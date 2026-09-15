"""Configuration and constants for TeamBuilder."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from SprelfPkmn.Objects import Regulation
from SprelfJSON import JSONModel, YAMLHelpers, DefaultFactory


class FormatContext(JSONModel):
    """Pokémon Champions format rules and defaults."""

    level: int = 50
    team_size: int = 6
    bring_size: int = 4
    item_clause: bool = True
    has_tera: bool = False
    has_gigantimax: bool = False
    has_z_moves: bool = False
    has_megas: bool = True
    regulation: Regulation = Regulation.M_C

class Config(JSONModel):
    config_dir: str
    dex_path: str | None = None
    moves_path: str | None = None
    cache_lifespan: int = 7
    ignore_cache: bool = False
    format: Annotated[FormatContext, DefaultFactory(FormatContext)] = FormatContext()
    color_enabled: bool | None = None

    """Global configuration."""
    _CONFIG: Config | None = None

    @classmethod
    def get(cls) -> Config:
        """Get the global configuration."""
        if cls._CONFIG is None:
            cls._CONFIG = cls.load()
        return cls._CONFIG

    @classmethod
    def load(cls) -> Config:
        config_dir = os.getenv("SPRELF_TEAM_DIR") or str(Path("~/.sprelf/teams").expanduser())
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        config_file = str(Path(config_dir) / "config.yaml")
        if os.path.exists(config_file):
            with open(config_file, "r", encoding="utf-8") as f:
                yml: dict = YAMLHelpers.load(f, default={})
                c = Config.from_json(yml)
        else:
            c = Config(config_dir=config_dir)
        if c.color_enabled is None:
            c.color_enabled = os.getenv("NO_COLOR") is None
        return c
