from __future__ import annotations

from datetime import datetime, timedelta, UTC
import httpx
import os
import json
import re
from pathlib import Path

from .Usage import UsageEntry, CommonSets, AbilityUsage, MoveUsage, ItemUsage, NatureUsage, \
    SpreadUsage
from .Database import Database
from EVHelperCLI.Config import Config
from SprelfPkmn import Item, Ability, Move, Nature, EVValue, Stat, Type, StatPoint

from SprelfJSON import JSONModel


class UsageCache(JSONModel):
    update: datetime
    entries: list[UsageEntry]

    @classmethod
    def path(cls) -> str:
        c = Config.get()
        return os.path.join(c.config_dir, "cache", "_usage.json")

    @classmethod
    def load(cls, path: str | None = None) -> UsageCache | None:
        path = path or cls.path()
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return cls.from_json(json.loads(f.read()))


class CommonSetsCache(JSONModel):
    name: str
    update: datetime
    entries: CommonSets

    @classmethod
    def path(cls, name: str) -> str:
        c = Config.get()
        return os.path.join(c.config_dir, "cache", f"{name}.json")

    @classmethod
    def load(cls, pokemon: str, path: str | None = None) -> CommonSetsCache | None:
        path = path or cls.path(pokemon)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return cls.from_json(json.loads(f.read()))


class DownloadCache:
    NORMALIZER_REGEX = re.compile(r"[^a-zA-Z0-9]")

    @classmethod
    def overall_usage(cls) -> list[UsageEntry]:
        c = Config.get()
        usage = UsageCache.load() if not c.ignore_cache else None

        now = datetime.now(tz=UTC)
        if c.ignore_cache or usage is None or now - usage.update > timedelta(days=c.cache_lifespan):
            usage = cls._download_overall_usage(last_update=usage.update if usage else None)
            if usage is None:
                return []
            p = Path(UsageCache.path())
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w") as f:
                f.write(json.dumps(usage.to_json()))

        return usage.entries

    @classmethod
    def _download_overall_usage(cls, last_update: datetime | None) -> UsageCache | None:
        url = "https://eurekaffeine.github.io/pokemon-champions-scraper/battle_meta.json"
        response = httpx.get(url,
                             headers={"If-Modified-Since": last_update.strftime("%a, %d %b %Y %H:%M:%S GMT")}
                             if last_update else {},
                             follow_redirects=True)
        if response.is_error:
            raise RuntimeError(f"Failed to download overall usage: ({response.status_code}) {response.text}")

        data = json.loads(response.text)
        updated = data["updated_at"] = datetime.strptime(data["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
        db = Database.get_pokemon()
        entries = [UsageEntry(pokemon=mon,
                              rank=p["rank"],
                              usage_percent=p.get("usage_rate"),
                              source="EurekaffeineScraper")
                   for p in data.get("pokemon_usage", [])
                   if (mon := db.showdown_name(p["name"])) is not None]
        return UsageCache(update=updated, entries=entries)

    @classmethod
    def common_sets(cls, pokemon: str) -> CommonSets | None:
        c = Config.get()
        common: CommonSetsCache | None = CommonSetsCache.load(pokemon) if not c.ignore_cache else None

        now = datetime.now(tz=UTC)
        if c.ignore_cache or common is None or now - common.update > timedelta(days=c.cache_lifespan):
            common = cls._download_common_sets(pokemon)
            if common is None:
                return None
            with open(CommonSetsCache.path(pokemon), "w") as f:
                json.dump(common.to_json(), f)
        return common.entries

    @classmethod
    def _download_common_sets(cls, pokemon: str) -> CommonSetsCache | None:
        if pokemon == "Floette":
            normalized = "floette-eternal"
        elif pokemon == "Maushold":
            normalized = "mausholdform1"
        elif pokemon == "Vivillon":
            normalized = "vivillonfancypattern"
        else:
            normalized = cls.NORMALIZER_REGEX.sub("", pokemon).lower()
        url = f"https://championsbattledata.com/api/battle/Doubles/{normalized}"

        response = httpx.get(url, follow_redirects=True)
        if response.is_error:
            raise RuntimeError(
                f"Failed to download common sets for '{pokemon}': ({response.status_code}) {response.text}")
        data = json.loads(response.text)
        updated = datetime.strptime(u, "%Y-%m-%dT%H:%M:%S.%fZ") \
            if (u := data.get("date")) else datetime.now(tz=UTC)
        db = Database.get_pokemon()
        mon = db.showdown_name(pokemon)
        if mon is None:
            return None
        common = CommonSets(pokemon=mon,
                            source="ChampionsBattleData")
        # This data is in the form of CSV, but has this JSON representation of the CSV.  We iterate through all
        # rows and grab the relevant usage data based on the "category" field of the row
        moves = Database.get_moves()
        for row in data.get("rows", []):
            perc = (row.get("percentage_value") or 0.) / 100.0

            match row.get("category"):
                case "move":
                    if m := moves.name(row.get("name")):
                        common.moves.append(MoveUsage(move=m,
                                                      percent=perc))
                case "held_item":
                    common.items.append(ItemUsage(item=Item(name=row.get("name", "?")),
                                                  percent=perc))
                case "teammate":
                    if mon := db.showdown_name(row.get("name")):
                        common.teammates.append(UsageEntry(pokemon=mon,
                                                           rank=row.get("rank", 0),
                                                           usage_percent=perc,
                                                           source="ChampionsBattleData"))
                case "stat_alignment":
                    if isinstance(n := getattr(Nature, row.get("name"), None), Nature):
                        common.natures.append(NatureUsage(nature=n,
                                                          percent=perc))
                case "stat_points":
                    common.spreads.append(SpreadUsage(evs={
                        Stat.HP: StatPoint(number=int(row.get("hp_points", 0))),
                        Stat.ATTACK: StatPoint(number=int(row.get("attack_points", 0))),
                        Stat.DEFENSE: StatPoint(number=int(row.get("defense_points", 0))),
                        Stat.SP_ATTACK: StatPoint(number=int(row.get("sp_atk_points", 0))),
                        Stat.SP_DEFENSE: StatPoint(number=int(row.get("sp_def_points", 0))),
                        Stat.SPEED: StatPoint(number=int(row.get("speed_points", 0)))
                    },
                        percent=perc))
                case "ability":
                    common.abilities.append(AbilityUsage(ability=Ability(name=row.get("name", "?")),
                                                         percent=perc))
        return CommonSetsCache(name=pokemon, update=updated, entries=common)
