from SprelfJSON import JSONModel

from SprelfPkmn import *

from EVHelperCLI.Config import Config

import os


#



class Database:

    _POKEMON: PokemonDataMap | None = None
    _MOVES: MoveDataMap | None = None

    @classmethod
    def load(cls):
        c = Config.get()
        cls._POKEMON = PokemonDataMap.from_file(os.path.join(c.config_dir, "dex.json"))
        cls._MOVES = MoveDataMap.from_file(os.path.join(c.config_dir, "moves.json"))

    @classmethod
    def get_pokemon(cls) -> PokemonDataMap:
        if cls._POKEMON is None:
            cls.load()
        assert cls._POKEMON is not None
        return cls._POKEMON

    @classmethod
    def get_moves(cls) -> MoveDataMap:
        if cls._MOVES is None:
            cls.load()
        assert cls._MOVES is not None
        return cls._MOVES

