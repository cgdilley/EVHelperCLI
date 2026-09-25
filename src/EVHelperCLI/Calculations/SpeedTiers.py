from __future__ import annotations

from SprelfJSON import JSONModel
from SprelfPkmn.Objects import *
from SprelfPkmn.Objects.Showdown import format_name
from SprelfPkmn.Calculations import get_stat_value

from typing import Iterable

from EVHelperCLI.Data.Usage import TopSet


#


class SpeedCalc(JSONModel):
    pokemon: Pokemon
    speed: int
    tailwind: bool = False
    own: bool = False

    @property
    def true_speed(self):
        return self.speed * 2 if self.tailwind else self.speed

    def __str__(self) -> str:
        return self.group_str(self.pokemon, speed=self.speed, tailwind=self.tailwind, own=self.own)

    @classmethod
    def group_str(cls, *pokemon: Pokemon, speed: int, tailwind: int, own: bool = False) -> str:
        s = f"{' ** ' if own else ''}"
        s += (f"[=={speed}==]  " if tailwind else f"[  {speed}  ]  ")
        mons = []
        for p in pokemon:
            is_boosting = p.stats.nature.is_boosting(Stat.SPEED)
            is_hindering = p.stats.nature.is_hindering(Stat.SPEED)
            mons.append(f"{p.data.showdown_name}  "
                f"( {p.stats.get_ev(Stat.SPEED).value(level=50)}"
                f"{'+' if is_boosting else '-' if is_hindering else ''} )")
        s += ", ".join(mons)
        s += f"  {'== IN TAILWIND ==' if tailwind else ''}"
        return s


class SpeedTiers:

    @classmethod
    def calculate(cls,
                  team: list[Pokemon],
                  top_sets: list[TopSet],
                  *,
                  own_tailwind: tuple[bool, ...] = (False,),
                  enemy_tailwind: tuple[bool, ...] = (False,)) -> list[SpeedCalc]:
        calcs = list(cls._get_all_speed_calcs(team, top_sets,
                                              own_tailwind=own_tailwind,
                                              enemy_tailwind=enemy_tailwind))
        return sorted(calcs, key=lambda calc: calc.true_speed, reverse=True)

    @classmethod
    def _get_all_speed_calcs(cls, team: list[Pokemon],
                             top_sets: list[TopSet],
                             own_tailwind: tuple[bool, ...] = (False,),
                             enemy_tailwind: tuple[bool, ...] = (False,)) -> Iterable[SpeedCalc]:
        for top_set in top_sets:
            speed_set: set[int] = set()
            for spread in top_set.sets.spreads[:4]:
                for nature in top_set.sets.natures[:4]:
                    for tw in enemy_tailwind:
                        speed_ev = spread.evs.get(Stat.SPEED, StatPoint(number=0))
                        speed = get_stat_value(stat=Stat.SPEED,
                                               base=top_set.entry.pokemon.stats.get_stat(Stat.SPEED),
                                               ev=speed_ev,
                                               iv=31, level=50, nature=nature.nature)
                        if speed in speed_set:
                            continue
                        speed_set.add(speed)

                        yield SpeedCalc(pokemon=Pokemon(data=top_set.entry.pokemon,
                                                        moveset=MoveSet(moves=[]),
                                                        typing=top_set.entry.pokemon.typing,
                                                        ability=top_set.entry.pokemon.abilities.primary,
                                                        stats=Stats(base=top_set.entry.pokemon.stats,
                                                                    evs={Stat.SPEED: speed_ev},
                                                                    ivs={Stat.SPEED: 31},
                                                                    level=50,
                                                                    nature=nature.nature),
                                                        item=None,
                                                        gender=None),
                                        speed=speed,
                                        tailwind=tw)

        for mon in team:
            for tw in own_tailwind:
                speed_ev = mon.stats.get_ev(Stat.SPEED)
                speed = get_stat_value(stat=Stat.SPEED,
                                       base=mon.data.stats.get_stat(Stat.SPEED),
                                       ev=speed_ev,
                                       iv=31, level=50, nature=mon.stats.nature)

                yield SpeedCalc(pokemon=mon,
                                speed=speed,
                                tailwind=tw,
                                own=True)
