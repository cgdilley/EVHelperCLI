from __future__ import annotations

from SprelfJSON import JSONModel
from SprelfPkmn import *


#


class UsageEntry(JSONModel):
    """One Pokémon's slice of the metagame."""

    pokemon: PokemonData
    rank: int
    usage_percent: float | None = None
    source: str = "Unknown source"


class MoveUsage(JSONModel):
    """A move and its usage frequency."""

    move: Move
    percent: float


class ItemUsage(JSONModel):
    """An item and its usage frequency."""

    item: Item
    percent: float


class AbilityUsage(JSONModel):
    """An ability and its usage frequency."""

    ability: Ability
    percent: float


class TeraUsage(JSONModel):
    """A Tera type and its usage frequency."""

    type: Type
    percent: float


class SpreadUsage(JSONModel):
    """An EV spread and its usage frequency."""

    evs: dict[Stat, TrainedValue]  # {STAT: value}
    percent: float


class NatureUsage(JSONModel):
    nature: Nature
    percent: float


class CommonSets(JSONModel):
    """Common movesets, items, abilities, and spreads for a Pokémon."""

    pokemon: PokemonData
    moves: list[MoveUsage] = []
    items: list[ItemUsage] = []
    abilities: list[AbilityUsage] = []
    spreads: list[SpreadUsage] = []
    natures: list[NatureUsage] = []
    teammates: list[UsageEntry] = []
    source: str = "Unknown source"


class TopSet(JSONModel):
    entry: UsageEntry
    sets: CommonSets
