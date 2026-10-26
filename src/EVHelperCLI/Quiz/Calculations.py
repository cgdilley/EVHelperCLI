import math
import random
import re
from abc import ABC
from typing import Sequence

from SprelfPkmn import (
    Stat,
    Nature,
    StatPoint,
    Pokemon,
    PokemonState,
    BoardState,
    calculate_damage,
    DamagingMove,
    MoveSet,
    Stats,
    EV,
    StatModifier,
    Weather,
    Terrain,
    Ability,
    DamageReport,
    get_stat_value_from_info,
)

from EVHelperCLI.Quiz.Quiz import NumberedQuiz, QuizPrompt, PromptResult, partial_credit, Style, colorize
from EVHelperCLI.Quiz.Common import short_stat_name
from EVHelperCLI.Data.Provider import UsageDataProvider
from EVHelperCLI.Data.Usage import TopSet


HINT_RANGE = "(e.g., '45-53%', '48%', or '120-142 HP'):"
HINT_KO = "(e.g., '1' for OHKO, '2' for 2HKO, or '2-3'):"


SETUP_BOOST_MOVES: dict[str, dict[Stat, int]] = {
    "Nasty Plot": {Stat.SP_ATTACK: 2},
    "Swords Dance": {Stat.ATTACK: 2},
    "Dragon Dance": {Stat.ATTACK: 1, Stat.SPEED: 1},
    "Calm Mind": {Stat.SP_ATTACK: 1, Stat.SP_DEFENSE: 1},
    "Quiver Dance": {Stat.SP_ATTACK: 1, Stat.SP_DEFENSE: 1, Stat.SPEED: 1},
    "Bulk Up": {Stat.ATTACK: 1, Stat.DEFENSE: 1},
    "Tail Glow": {Stat.SP_ATTACK: 3},
    "Curse": {Stat.ATTACK: 1, Stat.DEFENSE: 1},
    "Shell Smash": {Stat.ATTACK: 2, Stat.SP_ATTACK: 2, Stat.SPEED: 2},
}


def infer_weather(*abilities: Ability | None) -> Weather:
    names = {a.name for a in abilities if a is not None}
    if "Drought" in names:
        return Weather.SUN
    if "Drizzle" in names:
        return Weather.RAIN
    if "Sand Stream" in names:
        return Weather.SAND
    if "Snow Warning" in names:
        return Weather.SNOW
    return Weather.NONE


def infer_terrain(*abilities: Ability | None) -> Terrain:
    names = {a.name for a in abilities if a is not None}
    if "Grassy Surge" in names:
        return Terrain.GRASSY
    if "Electric Surge" in names:
        return Terrain.ELECTRIC
    if "Psychic Surge" in names:
        return Terrain.PSYCHIC
    if "Misty Surge" in names:
        return Terrain.MISTY
    return Terrain.NONE


def _format_pokemon_summary(state: PokemonState, is_attacker: bool = True) -> str:
    parts = [f"{state.data.name}"]
    if state.item:
        parts.append(f"@{state.item.name}")
    if state.ability:
        parts.append(f"({state.ability.name})")

    # Format EVs
    ev_parts = []
    if state.stats and hasattr(state.stats, "evs") and state.stats.evs:
        if isinstance(state.stats.evs, dict):
            for stat, ev_val in state.stats.evs.items():
                num = ev_val.number if isinstance(ev_val, StatPoint) else int(ev_val)
                if num > 0:
                    ev_parts.append(f"{num} {short_stat_name(stat)}")
        else:
            for ev in state.stats.evs:
                if hasattr(ev, "stat") and hasattr(ev, "number"):
                    num = ev.number.number if isinstance(ev.number, StatPoint) else int(ev.number)
                    if num > 0:
                        ev_parts.append(f"{num} {short_stat_name(ev.stat)}")
    ev_str = " / ".join(ev_parts) if ev_parts else "Default EVs"

    nature_str = state.stats.nature.name if state.stats and state.stats.nature else "Neutral"
    parts.append(f"[{nature_str}, {ev_str}]")

    # Modifiers
    if hasattr(state.stats, "modifiers") and state.stats.modifiers:
        mods = []
        for m, v in state.stats.modifiers.items():
            sign = "+" if v > 0 else ""
            mods.append(f"{sign}{v} {short_stat_name(m)}")
        if mods:
            parts.append(f"[{', '.join(mods)}]")

    return " ".join(parts)


class DamageCalcQuizPrompt(QuizPrompt, ABC):
    attacker: PokemonState
    defender: PokemonState
    move: DamagingMove
    board_state: BoardState
    report: DamageReport

    def _format_scenario_header(self) -> str:
        lines = [
            colorize("---------------- Battle Scenario ----------------", Style.BOLD, Style.CYAN),
            f"{colorize('Attacker :', Style.DIM)} {_format_pokemon_summary(self.attacker, is_attacker=True)}",
            f"{colorize('Defender :', Style.DIM)} {_format_pokemon_summary(self.defender, is_attacker=False)}",
            f"{colorize('Move     :', Style.DIM)} {colorize(self.move.name, Style.BOLD)}",
            colorize(" -" * 20, Style.DIM),
            f"{colorize('Calc     :', Style.DIM)} {colorize(str(self.report).split(':')[0].strip(), Style.YELLOW)}"
        ]
        field_conds = []
        if self.board_state.weather != Weather.NONE:
            field_conds.append(f"Weather: {self.board_state.weather.name.capitalize()}")
        if self.board_state.terrain != Terrain.NONE:
            field_conds.append(f"Terrain: {self.board_state.terrain.name.capitalize()}")
        if field_conds:
            lines.append(f"{colorize('Field    :', Style.DIM)} {colorize(', '.join(field_conds), Style.MAGENTA)}")
        lines.append(colorize("-------------------------------------------------", Style.CYAN))
        return "\n".join(lines)


class DamageRangePrompt(DamageCalcQuizPrompt):

    def get_prompt(self) -> str:
        header = self._format_scenario_header()
        return (
            f"{header}\n"
            f"{colorize('What is the approximate damage percentage range done to', Style.BOLD)} "
            f"{colorize(self.defender.data.name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}\n"
            f"{colorize(HINT_RANGE, Style.DIM)}"
        )

    def get_correct_answer(self) -> str:
        def_hp = get_stat_value_from_info(self.defender.stats, Stat.HP)
        actual_min_hp = self.report.rolls[0]
        actual_max_hp = self.report.rolls[-1]
        actual_min_pct = (actual_min_hp / def_hp) * 100.0
        actual_max_pct = (actual_max_hp / def_hp) * 100.0
        return f"{actual_min_hp}-{actual_max_hp} HP ({actual_min_pct:.1f} - {actual_max_pct:.1f}%)"

    def validate(self, answer: str) -> PromptResult:
        raw = answer.strip()
        numbers = [float(x) for x in re.findall(r"\b\d+(?:\.\d+)?\b", raw)]
        if not numbers:
            return PromptResult.as_incorrect(answer)

        def_hp = get_stat_value_from_info(self.defender.stats, Stat.HP)
        actual_min_hp = self.report.rolls[0]
        actual_max_hp = self.report.rolls[-1]
        actual_min_pct = (actual_min_hp / def_hp) * 100.0
        actual_max_pct = (actual_max_hp / def_hp) * 100.0
        actual_mid_pct = (actual_min_pct + actual_max_pct) / 2.0

        if len(numbers) >= 2:
            guess_min, guess_max = min(numbers[0], numbers[1]), max(numbers[0], numbers[1])
            # Check if user entered raw HP damage (e.g. "67-79" or "67-79 HP")
            if "%" not in raw:
                hp_diff = abs(((guess_min + guess_max) / 2.0) - ((actual_min_hp + actual_max_hp) / 2.0))
                pct_diff = abs(((guess_min + guess_max) / 2.0) - actual_mid_pct)
                if hp_diff < pct_diff or "hp" in raw.lower() or guess_max > 100.0:
                    guess_min = (guess_min / def_hp) * 100.0
                    guess_max = (guess_max / def_hp) * 100.0
            guess_mid = (guess_min + guess_max) / 2.0
        else:
            guess_val = numbers[0]
            if "%" not in raw and ("hp" in raw.lower() or guess_val > 100.0 or abs(guess_val - (actual_min_hp + actual_max_hp) / 2.0) < abs(guess_val - actual_mid_pct)):
                guess_val = (guess_val / def_hp) * 100.0
            guess_mid = guess_val
            guess_min = guess_val
            guess_max = guess_val

        diff = abs(guess_mid - actual_mid_pct)

        # Exact / excellent range match within 2% or inside roll range
        if (
            actual_min_pct - 1.0 <= guess_mid <= actual_max_pct + 1.0
            or diff <= 2.0
            or (abs(guess_min - actual_min_pct) <= 2.5 and abs(guess_max - actual_max_pct) <= 2.5)
        ):
            return PromptResult.as_correct(answer)

        value = partial_credit(diff, 25.0, exponent=0.8, decimals=3)
        if value is None:
            return PromptResult.as_incorrect(answer)
        return PromptResult.as_partial(answer, value)


class KnockoutPrognosisPrompt(DamageCalcQuizPrompt):

    def get_prompt(self) -> str:
        header = self._format_scenario_header()
        return (
            f"{header}\n"
            f"{colorize('How many hits are required for', Style.BOLD)} "
            f"{colorize(self.attacker.data.name.name, Style.BOLD, Style.YELLOW)} {colorize('to knock out', Style.BOLD)} "
            f"{colorize(self.defender.data.name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}\n"
            f"{colorize(HINT_KO, Style.DIM)}"
        )

    def get_correct_answer(self) -> str:
        return str(self.report)

    def get_feedback(self, result: PromptResult) -> str:
        return self.get_correct_answer()

    def validate(self, answer: str) -> PromptResult:
        raw = answer.strip().lower()
        if not raw:
            return PromptResult.as_incorrect(answer)

        def_hp = get_stat_value_from_info(self.defender.stats, Stat.HP)
        best_hits = math.ceil(def_hp / self.report.rolls[-1])
        worst_hits = math.ceil(def_hp / self.report.rolls[0])

        prognosis_hits, _ = self.report.get_knockout_prognosis()
        expected_hits = prognosis_hits or worst_hits

        # Parse user answer
        guess_hits: list[int] = []
        if "ohko" in raw or "1hko" in raw:
            guess_hits = [1]
        elif "2hko" in raw:
            guess_hits = [2]
        elif "3hko" in raw:
            guess_hits = [3]
        elif "4hko" in raw:
            guess_hits = [4]
        elif "5hko" in raw:
            guess_hits = [5]
        else:
            nums = [int(x) for x in re.findall(r"\b\d+\b", raw)]
            if nums:
                guess_hits = nums

        if not guess_hits:
            return PromptResult.as_incorrect(answer)

        user_min_hits = min(guess_hits)
        user_max_hits = max(guess_hits)

        # Check if guess matches actual prognosis or hits range
        if (user_min_hits == best_hits and user_max_hits == worst_hits) or (
            user_min_hits == expected_hits and user_max_hits == expected_hits
        ):
            return PromptResult.as_correct(answer)

        if best_hits <= user_min_hits <= worst_hits or best_hits <= user_max_hits <= worst_hits:
            return PromptResult.as_correct(answer)

        # Off by 1 hit gives partial credit
        min_diff = min(abs(user_min_hits - best_hits), abs(user_max_hits - worst_hits))
        if min_diff <= 1:
            return PromptResult.as_partial(answer, 0.5)

        return PromptResult.as_incorrect(answer)


def is_likely_attacker_move(
    attacker: Pokemon | PokemonState,
    move: DamagingMove,
) -> bool:
    """
    Filters out unlikely scenarios, such as a Pokémon with a high attack stat,
    attack boosting nature, and/or high attack investment, using a move that
    calculates damage based on special attack (and vice versa).
    """
    if not isinstance(move, DamagingMove):
        return False

    used_stat = getattr(move, "offense_stat", None)
    if used_stat not in (Stat.ATTACK, Stat.SP_ATTACK):
        return True

    opp_stat = Stat.SP_ATTACK if used_stat == Stat.ATTACK else Stat.ATTACK

    stats_obj = attacker.stats
    data_obj = attacker.data if hasattr(attacker, "data") else attacker

    # 1. Nature check
    if stats_obj and hasattr(stats_obj, "nature") and stats_obj.nature:
        nat = stats_obj.nature
        if nat.is_hindering(used_stat):
            return False
        if nat.is_boosting(opp_stat):
            return False

    # 2. EV investment check
    ev_used = 0
    ev_opp = 0
    if stats_obj and hasattr(stats_obj, "evs") and stats_obj.evs:
        if isinstance(stats_obj.evs, dict):
            ev_used_val = stats_obj.evs.get(used_stat, 0)
            ev_opp_val = stats_obj.evs.get(opp_stat, 0)
            ev_used = ev_used_val.number if isinstance(ev_used_val, StatPoint) else int(ev_used_val)
            ev_opp = ev_opp_val.number if isinstance(ev_opp_val, StatPoint) else int(ev_opp_val)
        else:
            for ev in stats_obj.evs:
                if hasattr(ev, "stat") and hasattr(ev, "number"):
                    num = ev.number.number if isinstance(ev.number, StatPoint) else int(ev.number)
                    if ev.stat == used_stat:
                        ev_used = num
                    elif ev.stat == opp_stat:
                        ev_opp = num

    if ev_opp >= 16 and ev_used <= 8:
        return False
    if ev_opp > ev_used and ev_opp >= 20:
        return False

    # 3. Base Stats check
    if hasattr(data_obj, "stats") and data_obj.stats:
        base_used = data_obj.stats.get_stat(used_stat)
        base_opp = data_obj.stats.get_stat(opp_stat)
        if base_opp >= base_used + 30 or (base_opp >= 100 and base_used <= 70) or base_opp >= 1.4 * base_used:
            return False

    # 4. Stat Modifiers check
    if stats_obj and hasattr(stats_obj, "modifiers") and stats_obj.modifiers:
        mod_used = stats_obj.modifiers.get(used_stat, 0)
        mod_opp = stats_obj.modifiers.get(opp_stat, 0)
        if mod_opp > 0 and mod_used <= 0:
            return False

    # 5. Calculated Stat Value check at level 50
    if stats_obj:
        val_used = get_stat_value_from_info(stats_obj, used_stat)
        val_opp = get_stat_value_from_info(stats_obj, opp_stat)
        if val_opp >= val_used + 35 or val_opp >= 1.35 * val_used:
            return False

    return True


def _build_pokemon_from_top_set(
    top_set: TopSet, is_attacker: bool = True
) -> tuple[Pokemon, list[DamagingMove], list[str]]:
    moves = [m.move for m in top_set.sets.moves]
    damaging_moves = [m for m in moves if isinstance(m, DamagingMove)]
    setup_moves = [m.name for m in moves if m.name in SETUP_BOOST_MOVES]

    item = top_set.sets.items[0].item if top_set.sets.items else None
    ability = top_set.sets.abilities[0].ability if top_set.sets.abilities else (
        list(top_set.entry.pokemon.abilities)[0] if top_set.entry.pokemon.abilities else None
    )
    nature = top_set.sets.natures[0].nature if top_set.sets.natures else Nature.build_neutral()

    if top_set.sets.spreads:
        spread = top_set.sets.spreads[0].evs
    else:
        # Default spread: offensive for attacker, bulky for defender
        if is_attacker:
            is_special = top_set.entry.pokemon.stats.get_stat(Stat.SP_ATTACK) > top_set.entry.pokemon.stats.get_stat(Stat.ATTACK)
            spread = {
                Stat.HP: StatPoint(number=0),
                Stat.ATTACK: StatPoint(number=0 if is_special else 32),
                Stat.DEFENSE: StatPoint(number=0),
                Stat.SP_ATTACK: StatPoint(number=32 if is_special else 0),
                Stat.SP_DEFENSE: StatPoint(number=0),
                Stat.SPEED: StatPoint(number=32),
            }
        else:
            spread = {
                Stat.HP: StatPoint(number=32),
                Stat.ATTACK: StatPoint(number=0),
                Stat.DEFENSE: StatPoint(number=16),
                Stat.SP_ATTACK: StatPoint(number=0),
                Stat.SP_DEFENSE: StatPoint(number=16),
                Stat.SPEED: StatPoint(number=0),
            }

    p = Pokemon(
        data=top_set.entry.pokemon,
        moveset=MoveSet(moves=damaging_moves[:4] if damaging_moves else moves[:4]),
        typing=top_set.entry.pokemon.typing,
        ability=ability,
        item=item,
        gender=None,
        stats=Stats.of(
            base=top_set.entry.pokemon.stats,
            evs=(EV(stat=k, number=v) for k, v in spread.items()),
            ivs=(),
            nature=nature,
            level=50,
        ),
    )
    return p, damaging_moves, setup_moves


def generate_scenario(
    top_sets: Sequence[TopSet],
    min_damage_cutoff: float = 0.20,
    rng: random.Random | None = None,
) -> tuple[PokemonState, PokemonState, DamagingMove, BoardState, DamageReport]:
    r = rng or random
    attempts = 0

    while attempts < 100:
        attempts += 1
        attacker_set = r.choice(top_sets)
        defender_set = r.choice(top_sets)

        attacker_mon, atk_moves, setup_moves = _build_pokemon_from_top_set(attacker_set, is_attacker=True)
        defender_mon, _, _ = _build_pokemon_from_top_set(defender_set, is_attacker=False)

        # Filter for likely moves for this attacker
        valid_moves = [m for m in atk_moves if is_likely_attacker_move(attacker_mon, m)]
        if not valid_moves:
            valid_moves = atk_moves

        if not valid_moves:
            continue

        move = r.choice(valid_moves)

        attacker_state = PokemonState.fresh(attacker_mon, team=0, slot=0)
        defender_state = PokemonState.fresh(defender_mon, team=1, slot=0)

        # Field conditions inferred from abilities
        weather = infer_weather(attacker_mon.ability, defender_mon.ability)
        terrain = infer_terrain(attacker_mon.ability, defender_mon.ability)
        board_state = BoardState(entities=[attacker_state, defender_state], weather=weather, terrain=terrain)

        # Setup boosts - choose boosting move compatible with the chosen move
        if setup_moves and r.random() < 0.4:
            move_stat = getattr(move, "offense_stat", None)
            compatible_setup = [
                sm for sm in setup_moves
                if move_stat is None or move_stat in SETUP_BOOST_MOVES.get(sm, {})
            ]
            boost_move = r.choice(compatible_setup) if compatible_setup else r.choice(setup_moves)
            boosts = SETUP_BOOST_MOVES[boost_move]
            for stat, boost in boosts.items():
                attacker_state.stats.add_modifiers(StatModifier(stat=stat, modifier=boost))

        # Re-verify that the complete scenario with modifiers is likely
        if not is_likely_attacker_move(attacker_state, move):
            continue

        report = calculate_damage(
            attacker=attacker_state,
            defender=defender_state,
            move=move,
            board_state=board_state,
            critical=False,
        )

        def_hp = get_stat_value_from_info(defender_state.stats, Stat.HP)
        if def_hp <= 0 or not report.rolls:
            continue

        min_damage_ratio = report.rolls[0] / def_hp
        if min_damage_ratio >= min_damage_cutoff:
            return attacker_state, defender_state, move, board_state, report

    # Fallback return whatever was last computed if cutoff was too strict
    return attacker_state, defender_state, move, board_state, report


class DamageCalcQuiz(NumberedQuiz[DamageCalcQuizPrompt]):

    PROMPT_TYPES = {
        "range": DamageRangePrompt,
        "ko": KnockoutPrognosisPrompt,
        "damage_range": DamageRangePrompt,
        "knockout": KnockoutPrognosisPrompt,
    }
    DEFAULT_PROMPT_TYPES = ["range", "ko"]
    TITLE = "Damage Calculations Quiz Results"
    TITLE_INDENT = 7

    def __init__(
        self,
        top_sets: Sequence[TopSet] | None = None,
        question_count: int = 10,
        allowed_prompt_types: Sequence[str] | None = None,
        inp=None,
        outp=None,
    ):
        super().__init__(
            question_count=question_count,
            allowed_prompt_types=allowed_prompt_types,
            inp=inp,
            outp=outp,
        )
        if top_sets is not None:
            self.top_sets = list(top_sets)
        else:
            provider = UsageDataProvider()
            self.top_sets = provider.top_common_sets(limit=30)

    def _generate_prompt(self) -> DamageCalcQuizPrompt:
        attacker, defender, move, board, report = generate_scenario(self.top_sets)
        chosen_type = random.choice(self.allowed_prompt_types)
        prompt_cls = self.PROMPT_TYPES[chosen_type]

        return prompt_cls(
            attacker=attacker,
            defender=defender,
            move=move,
            board_state=board,
            report=report,
        )
