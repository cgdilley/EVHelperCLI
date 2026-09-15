from SprelfJSON import JSONModel
from SprelfPkmn import *

from EVHelperCLI.Data import *

from typing import Iterable
from dataclasses import dataclass
import itertools


#


class NotableCalc(JSONModel):
    report: DamageReport
    offensive: bool


@dataclass
class _CalcOptions:
    items: list[Item]
    abilities: list[Ability]
    moves: list[DamagingMove]
    weathers: set[Weather]
    terrains: set[Terrain]
    spreads: list[dict[Stat, TrainedValue]]
    natures: set[Nature]
    critical: bool


@dataclass
class _CalcOptionSelection:
    item: Item
    ability: Ability
    move: DamagingMove
    weather: Weather
    terrain: Terrain
    spread: dict[Stat, TrainedValue]
    nature: Nature


class NotableCalculations:

    @classmethod
    def calculate(cls, team: list[Pokemon],
                  top_usage: list[TopSet],
                  *,
                  cutoff: float = 0.2,
                  weathers: set[Weather] | None = None,
                  terrains: set[Terrain] | None = None) -> Iterable[NotableCalc]:
        for pokemon in team:
            for top_set in top_usage:
                yield from cls.calculate_for_pairing(pokemon=pokemon, top_set=top_set, cutoff=cutoff,
                                                     weathers=weathers, terrains=terrains)

    @classmethod
    def calculate_for_pairing(cls, pokemon: Pokemon,
                              top_set: TopSet,
                              *,
                              cutoff: float = 0.2,
                              items: list[Item] | None = None,
                              abilities: list[Ability] | None = None,
                              moves: list[Move] | None = None,
                              weathers: set[Weather] | None = None,
                              terrains: set[Terrain] | None = None,
                              spreads: list[dict[Stat, StatPoint]] | None = None,
                              natures: set[Nature] | None = None,
                              critical: bool = False) -> Iterable[NotableCalc]:
        items = items or [i.item for i in top_set.sets.items if i.percent >= cutoff]
        abilities = abilities or [i.ability for i in top_set.sets.abilities if i.percent >= cutoff]
        moves = moves or [i.move for i in top_set.sets.moves if i.percent >= cutoff]
        damaging_moves = [m for m in moves if isinstance(m, DamagingMove)]
        if not weathers:
            weathers = cls._infer_weathers(pokemon.ability, *abilities)
        if not terrains:
            terrains = cls._infer_terrains(pokemon.ability, *abilities)

        spreads = spreads or [s.evs for s in top_set.sets.spreads[:5]]
        natures = natures or {n.nature for n in top_set.sets.natures if n.percent >= cutoff}

        # Defensive calcs
        yield from cls._run_calculations(
            pokemon=pokemon,
            top_set=top_set,
            offensive=False,
            options=_CalcOptions(
                moves=damaging_moves,
                weathers=weathers,
                terrains=terrains,
                items=items,
                abilities=abilities,
                spreads=spreads,
                natures=natures,
                critical=critical))

        # Offensive calcs
        yield from cls._run_calculations(
            pokemon=pokemon,
            top_set=top_set,
            offensive=True,
            options=_CalcOptions(
                moves=[m for m in pokemon.moveset.moves if isinstance(m, DamagingMove)],
                weathers=weathers,
                terrains=terrains,
                items=items,
                abilities=abilities,
                spreads=spreads,
                natures=natures,
                critical=critical))

    @classmethod
    def _infer_weathers(cls, *abilities: Ability) -> set[Weather]:
        all_abilities = {a.name for a in abilities}
        weathers = {Weather.NONE}
        if "Drought" in all_abilities:
            weathers.add(Weather.SUN)
        if "Sand Stream" in all_abilities:
            weathers.add(Weather.SAND)
        if "Drizzle" in all_abilities:
            weathers.add(Weather.RAIN)
        if "Snow Warning" in all_abilities:
            weathers.add(Weather.SNOW)
        return weathers

    @classmethod
    def _infer_terrains(cls, *abilities: Ability) -> set[Terrain]:
        all_abilities = {a.name for a in abilities}
        terrains = {Terrain.NONE}
        if "Grassy Surge" in all_abilities:
            terrains.add(Terrain.GRASSY)
        if "Electric Surge" in all_abilities:
            terrains.add(Terrain.ELECTRIC)
        if "Psychic Surge" in all_abilities:
            terrains.add(Terrain.PSYCHIC)
        if "Misty Surge" in all_abilities:
            terrains.add(Terrain.MISTY)
        return terrains

    @classmethod
    def _iterate_combinations(cls, offensive: bool,
                              options: _CalcOptions) -> Iterable[_CalcOptionSelection]:
        for move, weather, terrain, item, abil in itertools.product(options.moves,
                                                                    options.weathers,
                                                                    options.terrains,
                                                                    options.items,
                                                                    options.abilities):
            if offensive:
                unique_stat_pairs: set[tuple[int, ...]] = {(s[move.defense_stat].number, s[Stat.HP].number) for s in
                                                           options.spreads}
                unique_natures: set[Nature] = set(cls._get_relevant_natures(options.natures, move.defense_stat))
                for (stat, hp), nature in itertools.product(unique_stat_pairs, unique_natures):
                    stat_dict = {move.defense_stat: StatPoint(number=stat), Stat.HP: StatPoint(number=hp)}
                    yield _CalcOptionSelection(move=move,
                                               item=item,
                                               ability=abil,
                                               spread=stat_dict,
                                               nature=nature,
                                               weather=weather,
                                               terrain=terrain)
            else:
                unique_stats: set[int] = {s[move.offense_stat].number for s in options.spreads}
                unique_natures: set[Nature] = set(cls._get_relevant_natures(options.natures, move.offense_stat))
                for stat, nature in itertools.product(unique_stats, unique_natures):
                    yield _CalcOptionSelection(move=move,
                                               item=item,
                                               ability=abil,
                                               spread={move.offense_stat: StatPoint(number=stat)},
                                               nature=nature,
                                               weather=weather,
                                               terrain=terrain)

    @classmethod
    def _run_calculations(cls, pokemon: Pokemon,
                          top_set: TopSet,
                          offensive: bool,
                          options: _CalcOptions) -> Iterable[NotableCalc]:
        pokemon_state = PokemonState.fresh(pokemon, team=0, slot=0)
        unique_roll_sets: set[tuple[int, ...]] = set()

        for selection in cls._iterate_combinations(offensive=False, options=options):
            other_mon = Pokemon(data=top_set.entry.pokemon,
                                moveset=MoveSet(moves=[selection.move]),
                                typing=top_set.entry.pokemon.typing,
                                ability=selection.ability,
                                stats=Stats.of(base=top_set.entry.pokemon.stats,
                                               evs=(EV(stat=k, number=v) for k, v in selection.spread.items()),
                                               ivs=(),
                                               nature=selection.nature,
                                               level=50),
                                item=selection.item,
                                gender=None)
            other_state = PokemonState.fresh(other_mon, team=1, slot=0)
            state = BoardState(entities=[pokemon_state, other_state],
                               weather=selection.weather, terrain=selection.terrain)
            if selection.ability.name == "Fairy Aura":
                state.effects.append(BoardEffect(type=BoardEffectType.FAIRY_AURA,
                                                 targets=[pokemon_state, other_state]))

            if offensive:
                report = calculate_damage(attacker=pokemon_state, defender=other_state,
                                          move=selection.move, board_state=state, critical=options.critical)
            else:
                report = calculate_damage(attacker=other_state, defender=pokemon_state,
                                          move=selection.move, board_state=state, critical=options.critical)
            roll_key = tuple(report.rolls)
            if roll_key not in unique_roll_sets and cls._is_notable_calc(report):
                unique_roll_sets.add(roll_key)
                yield NotableCalc(report=report, offensive=False)

    @classmethod
    def _get_relevant_natures(cls, natures: Iterable[Nature], stat: Stat) -> Iterable[Nature]:

        nature_map: set[int] = set()
        for n in natures:
            if n.is_boosting(stat) and 1 not in nature_map:
                nature_map.add(1)
                yield n
            elif n.is_hindering(stat) and -1 not in nature_map:
                nature_map.add(-1)
                yield n
            elif 0 not in nature_map:
                nature_map.add(0)
                yield n

    @classmethod
    def _is_notable_calc(cls, report: DamageReport) -> bool:
        def_hp = get_stat_value_from_info(report.defender.stats, Stat.HP)
        low_perc = report.rolls[0] / def_hp
        high_perc = report.rolls[-1] / def_hp
        hits, perc = report.get_knockout_prognosis()
        if hits == 1 and low_perc <= 1.1:
            return True
        if hits == 2 and high_perc >= 0.9:
            return True
        return False
