
from unittest import TestCase

from EVHelperCLI import *
from SprelfPkmn import *
from EVHelperCLI.Calculations.Notable import NotableCalc, NotableCalculations
from EVHelperCLI.Calculations.SpeedTiers import SpeedTiers, SpeedCalc


class NotableCalcTests(TestCase):

    def test_notable_calc(self):
        paste = """Incineroar @ Sitrus Berry  
Ability: Intimidate  
Level: 50  
EVs: 30 HP / 5 Atk / 16 SpD / 15 Spe  
Adamant Nature  
- Flare Blitz  
- Darkest Lariat  
- Parting Shot  
- Fake Out
"""
        pokemon = parse_pokepaste(paste, Database.get_pokemon(), Database.get_moves())

        provider = UsageDataProvider()
        top_sets = provider.top_common_sets(limit=40)

        results = NotableCalculations.calculate(team=pokemon, top_usage=top_sets, calc_offensive=False,)
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
EVs: 14 HP / 28 Def / 24 Spe  
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
EVs: 32 Atk
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
        paste = """Gholdengo @ Life Orb
Ability: Good as Gold
EVs: 17 hp / 1 def / 13 spa / 21 spd / 14 spe
Modest Nature
- Protect
- Shadow Ball
- Nasty Plot
- Make It Rain

Volcarona @ Rocky Helmet
Ability: Flame Body
EVs: 32 hp / 16 def / 1 spd / 17 spe
Timid Nature
- Overheat
- Struggle Bug
- Rage Powder
- Tailwind

Garchomp-Mega-Z @ Garchompite Z
Ability: Rough Skin
EVs: 12 hp / 21 spa / 1 spd / 32 spe
Modest Nature
- Dragon Pulse
- Earth Power
- Power Gem
- Protect

Incineroar @ Sitrus Berry
Ability: Intimidate
EVs: 31 hp / 20 def / 13 spd / 2 spe
Impish Nature
- Parting Shot
- Fake Out
- Flare Blitz
- Darkest Lariat

Rillaboom @ Miracle Seed
Ability: Grassy Surge
EVs: 25 hp / 10 atk / 1 def / 30 spd
Adamant Nature
- Grassy Glide
- Wood Hammer
- Fake Out
- U-turn

Raichu-Mega-Y @ Raichunite Y
Ability: Lightning Rod
EVs: 29 hp / 5 def / 32 spe
Timid Nature
- Zap Cannon
- Focus Blast
- Fake Out
- Protect
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
