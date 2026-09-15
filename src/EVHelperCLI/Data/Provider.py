"""Abstract interface for usage data providers."""

from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
import httpx
import os

from SprelfJSON import JSONModel
from SprelfPkmn.Objects import Stat, Nature
from SprelfPkmn.Objects.Type import Type
from SprelfPkmn.Objects.CompetitiveInfo import Regulation
from SprelfPkmn.Utils import ShowdownUtils

from .DownloadCache import DownloadCache
from .Usage import UsageEntry, CommonSets, TopSet
from .VariantResolver import resolve_variants


class UsageDataProvider:
    """Abstract base for usage data sources."""

    def top_usage(
            self,
            limit: int = 30,
            regulation: Regulation | None = None,
    ) -> list[UsageEntry]:
        """
        Get the top Pokémon by usage.

        Args:
            limit: Maximum number of results (cap at 100).
            regulation: Regulation to filter by. If None, uses default.

        Returns:
            List of UsageEntry sorted by rank.
        """
        return DownloadCache.overall_usage()[:limit]

    def common_sets(
            self,
            name: str,
            regulation: Regulation | None = None,
    ) -> CommonSets | None:
        """
        Get common sets for a Pokémon.

        Args:
            name: The Pokémon's Showndown name.
            regulation: Regulation to filter by. If None, uses default.

        Returns:
            CommonSets if available, None otherwise.
        """
        return DownloadCache.common_sets(name)

    def top_common_sets(self, limit: int = 30, regulation: Regulation | None = None) -> list[TopSet]:
        top_sets = [
            TopSet(entry=usage_entry, sets=cs)
            for usage_entry in self.top_usage(limit=limit, regulation=regulation)
            if (cs := self.common_sets(usage_entry.pokemon.name.base_name(),
                                       regulation=regulation)) is not None
        ]
        resolved = [variant for ts in top_sets for variant in resolve_variants(ts)]
        if len(resolved) != len(top_sets):
            resolved = sorted(resolved, key=lambda ts: ts.entry.usage_percent, reverse=True)
            for i, r in enumerate(resolved):
                r.entry.rank = i + 1
        return resolved


    def describe_source(self) -> str:
        """Return a human-readable description of the data source."""
        return "Overall usage data is from https://eurekaffeine.github.io/.\n" \
               "Data on individual sets comes from https://championsbattledata.com/."
