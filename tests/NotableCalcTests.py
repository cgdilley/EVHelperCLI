
from unittest import TestCase

from EVHelperCLI import *
from SprelfPkmn import *
from EVHelperCLI.Calculations.Notable import NotableCalc, NotableCalculations
from EVHelperCLI.Calculations.SpeedTiers import SpeedTiers, SpeedCalc


class NotableCalcTests(TestCase):

    def test_notable_calc(self):
        paste = """Raichu-Mega-Y @ Raichunite Y  
Ability: Lightning Rod  
Level: 50  
EVs: 14 HP / 29 Def / 23 Spe  
Timid Nature  
- Protect  
- Zap Cannon  
- Fake Out  
- Focus Blast
"""
        pokemon = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        provider = UsageDataProvider()
        top_sets = provider.top_common_sets(limit=40)

        results = NotableCalculations.calculate(team=pokemon, top_usage=top_sets, calc_defensive=False,)
        closest_survival: tuple[NotableCalc, float] | None = None
        closest_ohko: tuple[NotableCalc, float] | None = None
        for calc in results:
            print(str(calc.report))
            hits, odds = calc.report.get_knockout_prognosis()
            if not calc.offensive and hits == 1 and (closest_ohko is None or odds < closest_ohko[1]):
                closest_ohko = (calc, odds)
            if not calc.offensive and hits == 2 and (closest_survival is None or odds > closest_survival[1]):
                closest_survival = (calc, odds)

        if closest_ohko is not None:
            print(f"CLOSEST OHKO: {closest_ohko[0].report}")
        if closest_survival is not None:
            print(f"CLOSEST SURVIVAL: {closest_survival[0].report}")


    def test_matchup_calc(self):
        paste = """Raichu-Mega-Y @ Raichunite Y  
Ability: Lightning Rod  
Level: 50  
EVs: 14 HP / 29 Def / 23 Spe  
Timid Nature  
- Protect  
- Zap Cannon  
- Fake Out  
- Focus Blast
"""
        player = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        paste = """Sneasler
EVs: 32 Atk
Adamant Nature  
- Close Combat
- Dire Claw

Sneasler
EVs: 32 Atk
- Close Combat
- Dire Claw

Salamence-Mega
EVs: 32 SpA
 - Draco Meteor
 
Golisopod-Mega
Adamant Nature
 - Leech Life

Farigiraf
 - Psychic

Gholdengo @ Life Orb
EVs: 32 SpA
Modest Nature
 - Make It Rain
 - Shadow Ball

Garchomp @ Life Orb
EVs: 32 Atk
Adamant Nature
 - Dragon Claw

Charizard-Mega-Y
EVs: 32 SpA
Modest Nature
 - Heat Wave

Garchomp-Mega-Z
EVs: 32 SpA
Modest Nature
 - Draco Meteor

Pawmot
EVs: 32 Atk
Adamant Nature
 - Close Combat

Primarina @ Life Orb
EVs: 32 SpA
Modest Nature
 - Moonblast

Rillaboom
EVs: 15 Atk
Adamant Nature
 - High Horsepower
"""
        target = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        for p in player:
            for t in target:
                for calc in NotableCalculations.calculate_matchup(p, t, BoardState(entities=[],
                                                                                   weather=Weather.SUN),
                                                                  calc_offensive=False):
                    print(str(calc.report))

    def test_speed_tiers(self):
        paste = """Raichu-Mega-Y @ Raichunite Y  
Ability: Lightning Rod  
Level: 50  
EVs: 14 HP / 29 Def / 23 Spe  
Timid Nature  
- Protect  
- Zap Cannon  
- Fake Out  
- Focus Blast  

Salamence-Mega @ Salamencite  
Ability: Intimidate  
Level: 50  
EVs: 23 HP / 11 SpA / 32 Spe  
Timid Nature  
- Protect  
- Hyper Voice  
- Tailwind  
- Draco Meteor  

Arcanine-Hisui @ Focus Sash  
Ability: Rock Head  
Level: 50  
EVs: 2 HP / 32 Atk / 32 Spe  
Jolly Nature  
- Protect  
- Flare Blitz  
- Extreme Speed  
- Head Smash  

Sylveon @ Fairy Feather  
Ability: Pixilate  
Level: 50  
EVs: 9 HP / 22 Def / 20 SpA / 15 Spe  
Modest Nature  
- Detect  
- Hyper Voice  
- Quick Attack  
- Hyper Beam  

Gholdengo @ Life Orb  
Ability: Good as Gold  
Level: 50  
EVs: 17 HP / 17 SpA / 32 Spe  
Timid Nature  
- Protect  
- Make It Rain  
- Nasty Plot  
- Shadow Ball  

Rillaboom @ Miracle Seed  
Ability: Grassy Surge  
Level: 50  
EVs: 18 HP / 25 Atk / 5 Def / 10 SpD / 8 Spe  
Adamant Nature  
- Wood Hammer  
- Grassy Glide  
- High Horsepower  
- Fake Out  
"""
        pokemon = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        provider = UsageDataProvider()
        top_sets = provider.top_common_sets(limit=40)

        own_tailwind = True

        grouped = {}
        for calc in SpeedTiers.calculate(team=pokemon, top_sets=top_sets,
                                         own_tailwind=(True, False)):
            grouped.setdefault((calc.true_speed, calc.own, calc.tailwind), []).append(calc)
        for (s, own, tw), grp in sorted(grouped.items(), key=lambda x: x[0], reverse=True):
            print(SpeedCalc.group_str(*(p.pokemon for p in grp), speed=s,
                                      tailwind=tw,
                                      own=own))
