import random
import re
from abc import ABC
from typing import Sequence

from SprelfPkmn import (
    Stat,
    Nature,
    StatPoint,
    PokemonData,
    get_stat_value,
)
from SprelfPkmn.Objects.Stats import NATURE_MAP, NUMBER_STATS

from EVHelperCLI.Quiz.Quiz import NumberedQuiz, QuizPrompt, PromptResult, partial_credit, Style, colorize
from EVHelperCLI.Quiz.Common import format_stat_name, parse_first_int, normalize_name
from EVHelperCLI.Data.Provider import UsageDataProvider
from EVHelperCLI.Data.Database import Database

HINT_COMPARE = "Enter >, <, or = (or 'greater', 'lesser', 'equal'):"
HINT_EV_NATURE = "(e.g., '32 Jolly' or '0 Modest')"

NATURE_NAME_TO_NATURE: dict[str, Nature] = {
    name.lower(): getattr(Nature, name.upper())
    for name in set(NATURE_MAP.values())
    if hasattr(Nature, name.upper())
}

# Stat weights: give Speed a higher weight for competitive memorization
STAT_WEIGHTS = {
    Stat.SPEED: 0.35,
    Stat.ATTACK: 0.15,
    Stat.SP_ATTACK: 0.15,
    Stat.HP: 0.15,
    Stat.DEFENSE: 0.10,
    Stat.SP_DEFENSE: 0.10,
}


def pick_weighted_stat(rng: random.Random | None = None) -> Stat:
    r = rng or random
    stats = list(STAT_WEIGHTS.keys())
    weights = [STAT_WEIGHTS[s] for s in stats]
    return r.choices(stats, weights=weights, k=1)[0]


def is_stat_ignored(p: PokemonData, stat: Stat) -> bool:
    if stat not in (Stat.ATTACK, Stat.SP_ATTACK):
        return False
    atk = p.stats.get_stat(Stat.ATTACK)
    spa = p.stats.get_stat(Stat.SP_ATTACK)
    own, other = (atk, spa) if stat == Stat.ATTACK else (spa, atk)
    return other - own >= 30 and own < 100


class BaseStatsQuizPrompt(QuizPrompt, ABC):
    pass


class ExactBaseStatPrompt(BaseStatsQuizPrompt):
    pokemon: PokemonData
    stat: Stat

    def get_prompt(self) -> str:
        stat_name = format_stat_name(self.stat)
        return (
            f"{colorize('What is the base', Style.BOLD)} {colorize(stat_name, Style.BOLD, Style.CYAN)} "
            f"{colorize('of', Style.BOLD)} {colorize(self.pokemon.name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        )

    def get_correct_answer(self) -> str:
        actual = self.pokemon.stats.get_stat(self.stat)
        return f"{actual} (Base {format_stat_name(self.stat)})"

    def validate(self, answer: str) -> PromptResult:
        guess = parse_first_int(answer)
        if guess is None:
            return PromptResult.as_incorrect(answer)

        actual = self.pokemon.stats.get_stat(self.stat)

        if guess == actual:
            return PromptResult.as_correct(answer)

        # Partial credit if within 5 points
        value = partial_credit(abs(guess - actual), 15, decimals=2, scale=20)
        if value is None:
            return PromptResult.as_incorrect(answer)
        return PromptResult.as_partial(answer, value)


class CompareBaseStatPrompt(BaseStatsQuizPrompt):
    pokemon1: PokemonData
    pokemon2: PokemonData
    stat: Stat

    def get_prompt(self) -> str:
        stat_name = format_stat_name(self.stat)
        return (
            f"{colorize('How does the base', Style.BOLD)} {colorize(stat_name, Style.BOLD, Style.CYAN)} "
            f"{colorize('of', Style.BOLD)} {colorize(self.pokemon1.name.name, Style.BOLD, Style.YELLOW)} "
            f"{colorize('compare to', Style.BOLD)} {colorize(self.pokemon2.name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}\n"
            f"{colorize(HINT_COMPARE, Style.DIM)}"
        )

    def get_correct_answer(self) -> str:
        stat1 = self.pokemon1.stats.get_stat(self.stat)
        stat2 = self.pokemon2.stats.get_stat(self.stat)
        sym = ">" if stat1 > stat2 else ("<" if stat1 < stat2 else "=")
        return f"{sym} ({self.pokemon1.name}: {stat1} vs. {self.pokemon2.name}: {stat2})"

    def validate(self, answer: str) -> PromptResult:
        raw = answer.strip().lower()
        stat1 = self.pokemon1.stats.get_stat(self.stat)
        stat2 = self.pokemon2.stats.get_stat(self.stat)

        if stat1 > stat2:
            expected = ">"
        elif stat1 < stat2:
            expected = "<"
        else:
            expected = "="

        norm = None
        if raw in (">", "greater", "higher", "more", "faster", "stronger", "better", "above"):
            norm = ">"
        elif raw in ("<", "less", "lesser", "lower", "fewer", "slower", "weaker", "worse", "below"):
            norm = "<"
        elif raw in ("=", "==", "equal", "same", "tied", "tie", "equals", "equal to"):
            norm = "="

        if norm == expected:
            return PromptResult.as_correct(answer)
        return PromptResult.as_incorrect(answer)


OPTION_LABELS = "ABCDE"


class SameBaseStatPrompt(BaseStatsQuizPrompt):
    pokemon: PokemonData
    stat: Stat
    target_value: int
    options: list[str] = []
    correct_option: str = ""

    def get_prompt(self) -> str:
        stat_name = format_stat_name(self.stat)
        lines = [
            f"{colorize('Which Pokémon has the same base', Style.BOLD)} "
            f"{colorize(stat_name, Style.BOLD, Style.CYAN)} "
            f"{colorize(f'({self.target_value})', Style.BOLD, Style.YELLOW)} "
            f"{colorize('as', Style.BOLD)} {colorize(self.pokemon.name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        ]
        for label, name in zip(OPTION_LABELS, self.options):
            lines.append(f"  {label}) {name}")
        lines.append(colorize("(Enter a letter, number, or name)", Style.DIM))
        return "\n".join(lines)

    def get_correct_answer(self) -> str:
        return f"{self.correct_option} (Base {format_stat_name(self.stat)} {self.target_value})"

    def get_feedback(self, result: PromptResult) -> str:
        return self.get_correct_answer()

    def validate(self, answer: str) -> PromptResult:
        raw = answer.strip()
        if not raw:
            return PromptResult.as_incorrect(answer)

        lowered = raw.lower()
        index: int | None = None
        if len(lowered) == 1 and lowered in OPTION_LABELS.lower()[:len(self.options)]:
            index = OPTION_LABELS.lower().index(lowered)
        elif lowered.isdigit() and 1 <= int(lowered) <= len(self.options):
            index = int(lowered) - 1
        else:
            norm = normalize_name(raw)
            for i, name in enumerate(self.options):
                if normalize_name(name) == norm:
                    index = i
                    break

        if index is None:
            return PromptResult.as_incorrect(answer)
        if self.options[index] == self.correct_option:
            return PromptResult.as_correct(answer)
        return PromptResult.as_incorrect(answer)


class AdjustedStatValuePrompt(BaseStatsQuizPrompt):
    pokemon: PokemonData | None = None
    base_stat: int
    stat: Stat
    ev: StatPoint
    iv: int = 31
    nature: Nature = Nature.build_neutral()
    level: int = 50

    def get_prompt(self) -> str:
        stat_name = format_stat_name(self.stat)
        nature_name = self.nature.name if self.nature else "Neutral"
        ev_points = self.ev.number if isinstance(self.ev, StatPoint) else int(self.ev)

        if self.pokemon:
            return (
                f"{colorize('What is', Style.BOLD)} {colorize(stat_name, Style.BOLD, Style.CYAN)} "
                f"{colorize('of', Style.BOLD)} {colorize(self.pokemon.name.name, Style.BOLD, Style.YELLOW)} "
                f"{colorize(f'(Base {self.base_stat})', Style.DIM)} "
                f"{colorize('with', Style.BOLD)} {colorize(f'{ev_points} stat points', Style.BOLD)} "
                f"{colorize('and a', Style.BOLD)} {colorize(nature_name, Style.MAGENTA)} "
                f"{colorize('nature?', Style.BOLD)}"
            )
        else:
            return (
                f"What is the {stat_name} of a Pokémon with "
                f"Base {self.base_stat}, {ev_points} stat points, "
                f"and a {nature_name} nature?"
            )

    def get_correct_answer(self) -> str:
        expected = get_stat_value(
            stat=self.stat,
            base=self.base_stat,
            ev=self.ev,
            iv=self.iv,
            level=self.level,
            nature=self.nature,
        )
        return f"{expected}"

    def validate(self, answer: str) -> PromptResult:
        guess = parse_first_int(answer)
        if guess is None:
            return PromptResult.as_incorrect(answer)

        expected = get_stat_value(
            stat=self.stat,
            base=self.base_stat,
            ev=self.ev,
            iv=self.iv,
            level=self.level,
            nature=self.nature,
        )

        if guess == expected:
            return PromptResult.as_correct(answer)

        value = partial_credit(abs(guess - expected), 20, exponent=0.8, decimals=3)
        if value is None:
            return PromptResult.as_incorrect(answer)
        return PromptResult.as_partial(answer, value)


class EVForStatPrompt(BaseStatsQuizPrompt):
    pokemon: PokemonData
    stat: Stat
    target_stat_value: int
    given_nature: Nature | None = None
    level: int = 50
    iv: int = 31

    def get_prompt(self) -> str:
        stat_name = format_stat_name(self.stat)
        base = self.pokemon.stats.get_stat(self.stat)
        if self.given_nature:
            return (
                f"{colorize('How many EVs / StatPoints (0-32) are needed for', Style.BOLD)} "
                f"{colorize(self.pokemon.name.name, Style.BOLD, Style.YELLOW)} {colorize(f'(Base {base})', Style.DIM)} "
                f"{colorize('to reach', Style.BOLD)} {colorize(f'{self.target_stat_value} {stat_name}', Style.BOLD, Style.CYAN)} "
                f"{colorize('with a', Style.BOLD)} {colorize(self.given_nature.name, Style.MAGENTA)} "
                f"{colorize('nature?', Style.BOLD)}"
            )
        else:
            return (
                f"{colorize('What EV investment (StatPoints 0-32) and Nature are needed for', Style.BOLD)} "
                f"{colorize(self.pokemon.name.name, Style.BOLD, Style.YELLOW)} {colorize(f'(Base {base})', Style.DIM)} "
                f"{colorize('to reach', Style.BOLD)} {colorize(f'{self.target_stat_value} {stat_name}', Style.BOLD, Style.CYAN)}{colorize('?', Style.BOLD)}\n"
                f"{colorize(HINT_EV_NATURE, Style.DIM)}"
            )

    def get_correct_answer(self) -> str:
        base = self.pokemon.stats.get_stat(self.stat)
        solutions = []
        if self.given_nature:
            for pt in range(33):
                val = get_stat_value(self.stat, base, StatPoint(number=pt), self.iv, self.level, self.given_nature)
                if val == self.target_stat_value:
                    solutions.append(f"{pt} StatPoints ({pt * 8} EVs)")
        else:
            # Check all natures
            for nat_name, nat in NATURE_NAME_TO_NATURE.items():
                for pt in range(33):
                    val = get_stat_value(self.stat, base, StatPoint(number=pt), self.iv, self.level, nat)
                    if val == self.target_stat_value:
                        solutions.append(f"{pt} {nat.name}")
                        break
        if solutions:
            return ", ".join(solutions[:4])
        return f"Target stat value: {self.target_stat_value}"

    def validate(self, answer: str) -> PromptResult:
        raw = answer.strip()
        # Parse number (StatPoint)
        num_match = re.search(r"\b(\d+)\b", raw)
        if not num_match:
            return PromptResult.as_incorrect(answer)

        parsed_num = int(num_match.group(1))
        # Handle traditional EV input (e.g. 252 -> 32, 4 -> 1, 12 -> 2)
        if parsed_num > 32:
            if parsed_num >= 252:
                parsed_statpoint = 32
            elif parsed_num >= 4:
                parsed_statpoint = 1 + (parsed_num - 4) // 8
            else:
                parsed_statpoint = 0
        else:
            parsed_statpoint = min(32, max(0, parsed_num))

        # Parse nature from answer if not given
        parsed_nature = self.given_nature
        if parsed_nature is None:
            for word in re.findall(r"[a-zA-Z]+", raw):
                lower_word = word.lower()
                if lower_word in NATURE_NAME_TO_NATURE:
                    parsed_nature = NATURE_NAME_TO_NATURE[lower_word]
                    break

        base = self.pokemon.stats.get_stat(self.stat)
        effective_nature = parsed_nature or self.given_nature or Nature.build_neutral()
        achieved_stat = get_stat_value(
            stat=self.stat,
            base=base,
            ev=StatPoint(number=parsed_statpoint),
            iv=self.iv,
            level=self.level,
            nature=effective_nature,
        )

        if achieved_stat == self.target_stat_value:
            return PromptResult.as_correct(answer)

        value = partial_credit(abs(achieved_stat - self.target_stat_value), 4, decimals=2, scale=10)
        if value is None:
            return PromptResult.as_incorrect(answer)
        return PromptResult.as_partial(answer, value)


class BaseStatsQuiz(NumberedQuiz[BaseStatsQuizPrompt]):
    PROMPT_TYPES = {
        "exact": ExactBaseStatPrompt,
        "compare": CompareBaseStatPrompt,
        "same": SameBaseStatPrompt,
        "adjusted": AdjustedStatValuePrompt,
        "ev_calc": EVForStatPrompt,
    }
    PROMPT_WEIGHTS = {
        "exact": 0.30,
        "compare": 0.25,
        "same": 0.15,
        "adjusted": 0.15,
        "ev_calc": 0.15,
    }
    TITLE = "Base Stats Quiz Results"
    TITLE_INDENT = 10

    def __init__(
            self,
            pokemon_pool: Sequence[PokemonData] | None = None,
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
        if pokemon_pool is not None:
            self.pokemon_pool = list(pokemon_pool)
        else:
            provider = UsageDataProvider()
            top = provider.top_common_sets(limit=100)
            self.pokemon_pool = [e.entry.pokemon for e in top if e.entry is not None and e.entry.pokemon is not None]

    def _generate_prompt(self) -> BaseStatsQuizPrompt:
        active_types = [t for t in self.allowed_prompt_types if t in self.PROMPT_WEIGHTS]
        active_weights = [self.PROMPT_WEIGHTS[t] for t in active_types]

        prompt_type = random.choices(active_types, weights=active_weights, k=1)[0]

        if prompt_type == "same":
            return self._generate_same_prompt()

        p, stat = self._pick_pokemon_and_stat()
        generators = {
            "exact": self._generate_exact,
            "compare": self._generate_compare,
            "adjusted": self._generate_adjusted,
            "ev_calc": self._generate_ev_calc,
        }
        return generators[prompt_type](p, stat)

    def _pick_pokemon_and_stat(self) -> tuple[PokemonData, Stat]:
        while True:
            p = random.choice(self.pokemon_pool)
            stat = pick_weighted_stat()
            if not is_stat_ignored(p, stat):
                return p, stat

    @staticmethod
    def _generate_exact(p: PokemonData, stat: Stat) -> BaseStatsQuizPrompt:
        return ExactBaseStatPrompt(pokemon=p, stat=stat)

    def _generate_compare(self, p: PokemonData, stat: Stat) -> BaseStatsQuizPrompt:
        p2 = random.choice(self.pokemon_pool)
        while p2.showdown_name == p.showdown_name and len(self.pokemon_pool) > 1:
            p2 = random.choice(self.pokemon_pool)
        return CompareBaseStatPrompt(pokemon1=p, pokemon2=p2, stat=stat)

    def _generate_same_prompt(self) -> BaseStatsQuizPrompt:
        # all_pokemon = list(Database.get_pokemon().list())
        while True:
            p = random.choice(self.pokemon_pool)
            first = pick_weighted_stat()
            stats = [first] + [s for s in NUMBER_STATS if s != first]
            for stat in stats:
                if is_stat_ignored(p, stat):
                    continue
                built = self._build_same_options(p, stat, self.pokemon_pool)
                if built is None:
                    continue
                correct, distractors = built
                options = [correct] + distractors
                random.shuffle(options)
                return SameBaseStatPrompt(
                    pokemon=p,
                    stat=stat,
                    target_value=p.stats.get_stat(stat),
                    options=[o.name.name for o in options],
                    correct_option=correct.name.name,
                )

    @staticmethod
    def _build_same_options(
            p: PokemonData,
            stat: Stat,
            all_pokemon: list[PokemonData],
    ) -> tuple[PokemonData, list[PokemonData]] | None:
        target = p.stats.get_stat(stat)
        others = [q for q in all_pokemon if q.showdown_name != p.showdown_name]
        valid = [q for q in others if q.stats.get_stat(stat) == target]
        if not valid:
            return None
        near = [q for q in others if q.stats.get_stat(stat) != target]
        near.sort(key=lambda q: abs(q.stats.get_stat(stat) - target))
        nearest = near[:20]
        if len(nearest) < 4:
            return None
        return random.choice(valid), random.sample(nearest, 4)

    @staticmethod
    def _generate_adjusted(p: PokemonData, stat: Stat) -> BaseStatsQuizPrompt:
        base = p.stats.get_stat(stat)
        ev = StatPoint(number=random.choice([0, 4, 12, 20, 28, 32]))
        nature = random.choice([
            Nature.build_neutral(),
            Nature.build_boosting(stat),
            Nature.build_hindering(stat),
        ])
        use_pkmn = random.random() < 0.6
        return AdjustedStatValuePrompt(
            pokemon=p if use_pkmn else None,
            base_stat=base,
            stat=stat,
            ev=ev,
            iv=31,
            nature=nature,
            level=50,
        )

    @staticmethod
    def _generate_ev_calc(p: PokemonData, stat: Stat) -> BaseStatsQuizPrompt:
        base = p.stats.get_stat(stat)
        ev_pt = random.choice([0, 4, 8, 16, 24, 32])
        nature = random.choice([
            Nature.build_neutral(),
            Nature.build_boosting(stat),
        ])
        target_val = get_stat_value(stat, base, StatPoint(number=ev_pt), 31, 50, nature)
        given_nature = nature if random.random() < 0.5 else None
        return EVForStatPrompt(
            pokemon=p,
            stat=stat,
            target_stat_value=target_val,
            given_nature=given_nature,
            level=50,
            iv=31,
        )
