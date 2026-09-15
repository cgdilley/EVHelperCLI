
from unittest import TestCase

from EVHelperCLI import *
from SprelfPkmn import *


class NotableCalcTests(TestCase):

    def test_notable_calc(self):
        paste = """Rillaboom @ Miracle Seed  
Ability: Grassy Surge  
Level: 50  
EVs: 32 HP / 32 Atk / 2 Spe  
Adamant Nature  
- Grassy Glide  
- Wood Hammer  
- Drain Punch  
- U-turn"""
        pokemon = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        provider = UsageDataProvider()
        top_sets = provider.top_common_sets(limit=30)

        for calc in NotableCalculations.calculate(team=pokemon, top_usage=top_sets, terrains={Terrain.GRASSY}):
            print(str(calc.report))
