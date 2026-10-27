import unittest
from unittest import TestCase

from SprelfPkmn import (
    Stat,
    Nature,
    StatPoint,
    Pokemon,
    PokemonState,
    BoardState,
    calculate_damage,
    MoveSet,
    Stats,
    EV,
    DamagingMove,
    Weather,
    Terrain,
    Ability,
    Item,
    get_stat_value,
    StatModifier,
)
from EVHelperCLI.Data.Database import Database
from EVHelperCLI.Data.Provider import UsageDataProvider
from EVHelperCLI.Data.Usage import TopSet, CommonSets, MoveUsage, ItemUsage, AbilityUsage, NatureUsage, UsageEntry
from EVHelperCLI.Quiz import (
    AnswerType,
    BaseStatsQuiz,
    ExactBaseStatPrompt,
    CompareBaseStatPrompt,
    SameBaseStatPrompt,
    AdjustedStatValuePrompt,
    EVForStatPrompt,
    MetagameQuiz,
    TopMovePrompt,
    TopItemPrompt,
    TopAbilityPrompt,
    TopNaturePrompt,
    DamageCalcQuiz,
    DamageRangePrompt,
    KnockoutPrognosisPrompt,
)
from EVHelperCLI.Quiz.Calculations import (
    infer_weather,
    infer_terrain,
    generate_scenario,
    is_likely_attacker_move,
)


class QuizTests(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = Database.get_pokemon()
        cls.moves_db = Database.get_moves()
        cls.garchomp = list(cls.db.name("Garchomp"))[0]
        cls.salamence = list(cls.db.name("Salamence"))[0]
        cls.rillaboom = list(cls.db.name("Rillaboom"))[0]

    def test_exact_base_stat_prompt(self):
        prompt = ExactBaseStatPrompt(pokemon=self.garchomp, stat=Stat.SPEED)
        self.assertIn("Garchomp", prompt.get_prompt())
        self.assertIn("Speed", prompt.get_prompt())

        # Exact match (Garchomp base speed = 102)
        res_exact = prompt.validate("102")
        self.assertEqual(res_exact.result, AnswerType.CORRECT)
        self.assertEqual(res_exact.value, 1.0)

        # Off by 2 (within 5 points -> partial credit)
        res_near = prompt.validate("100")
        self.assertEqual(res_near.result, AnswerType.PARTIAL)
        self.assertEqual(res_near.value, 0.8)

        # Off by 5 (boundary of partial credit)
        res_bound = prompt.validate("97")
        self.assertEqual(res_bound.result, AnswerType.PARTIAL)
        self.assertEqual(res_bound.value, 0.5)

        # Off by 6 (too far)
        res_far = prompt.validate("96")
        self.assertEqual(res_far.result, AnswerType.INCORRECT)
        self.assertEqual(res_far.value, 0.0)

        # Non-numeric input
        res_invalid = prompt.validate("fast")
        self.assertEqual(res_invalid.result, AnswerType.INCORRECT)
        self.assertEqual(res_invalid.value, 0.0)

    def test_compare_base_stat_prompt(self):
        # Garchomp base Speed: 102, Salamence base Speed: 100
        prompt = CompareBaseStatPrompt(pokemon1=self.garchomp, pokemon2=self.salamence, stat=Stat.SPEED)

        self.assertEqual(prompt.validate(">").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("greater").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("faster").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("higher").result, AnswerType.CORRECT)

        self.assertEqual(prompt.validate("<").result, AnswerType.INCORRECT)
        self.assertEqual(prompt.validate("lesser").result, AnswerType.INCORRECT)
        self.assertEqual(prompt.validate("=").result, AnswerType.INCORRECT)

        # Salamence vs Garchomp
        prompt2 = CompareBaseStatPrompt(pokemon1=self.salamence, pokemon2=self.garchomp, stat=Stat.SPEED)
        self.assertEqual(prompt2.validate("<").result, AnswerType.CORRECT)
        self.assertEqual(prompt2.validate("slower").result, AnswerType.CORRECT)
        self.assertEqual(prompt2.validate(">").result, AnswerType.INCORRECT)

    def test_same_base_stat_prompt(self):
        prompt = SameBaseStatPrompt(
            pokemon=self.garchomp,
            stat=Stat.SPEED,
            target_value=102,
            options=["Garchomp", "Pikachu", "Delphox", "Salamence", "Rillaboom"],
            correct_option="Delphox",
        )

        self.assertIn("A) Garchomp", prompt.get_prompt())
        self.assertEqual(prompt.validate("C").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("3").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("delphox").result, AnswerType.CORRECT)
        self.assertEqual(prompt.validate("A").result, AnswerType.INCORRECT)
        self.assertEqual(prompt.validate("NotARealPokemon").result, AnswerType.INCORRECT)

    def test_adjusted_stat_value_prompt(self):
        # Level 50 Garchomp: Base 102 Speed, 32 StatPoints (252 EVs), 31 IV, Jolly (+Spe) -> 169
        expected = get_stat_value(Stat.SPEED, 102, StatPoint(number=32), 31, 50, Nature.JOLLY)
        self.assertEqual(expected, 169)

        prompt = AdjustedStatValuePrompt(
            pokemon=self.garchomp,
            base_stat=102,
            stat=Stat.SPEED,
            ev=StatPoint(number=32),
            iv=31,
            nature=Nature.JOLLY,
            level=50,
        )

        # Exact match
        res_exact = prompt.validate("169")
        self.assertEqual(res_exact.result, AnswerType.CORRECT)
        self.assertEqual(res_exact.value, 1.0)

        # Close guess (off by 2)
        res_close = prompt.validate("167")
        self.assertEqual(res_close.result, AnswerType.PARTIAL)
        self.assertGreater(res_close.value, 0.8)

        # Far guess
        res_far = prompt.validate("100")
        self.assertEqual(res_far.result, AnswerType.INCORRECT)
        self.assertEqual(res_far.value, 0.0)

    def test_ev_for_stat_prompt(self):
        # Garchomp base 102 Speed, target 169 with Jolly nature requires 32 StatPoints
        prompt = EVForStatPrompt(
            pokemon=self.garchomp,
            stat=Stat.SPEED,
            target_stat_value=169,
            given_nature=Nature.JOLLY,
            level=50,
            iv=31,
        )

        # Exact match
        res_exact = prompt.validate("32")
        self.assertEqual(res_exact.result, AnswerType.CORRECT)
        self.assertEqual(res_exact.value, 1.0)

        # Traditional 252 EV notation should also normalize to 32 StatPoints
        res_trad = prompt.validate("252")
        self.assertEqual(res_trad.result, AnswerType.CORRECT)

        # Partial credit (off by 2 StatPoints)
        res_part = prompt.validate("30")
        self.assertEqual(res_part.result, AnswerType.PARTIAL)
        self.assertGreater(res_part.value, 0.5)

        # When nature is not given in prompt and asked to provide both EV and Nature
        prompt_with_nature_query = EVForStatPrompt(
            pokemon=self.garchomp,
            stat=Stat.SPEED,
            target_stat_value=169,
            given_nature=None,
            level=50,
            iv=31,
        )
        res_both = prompt_with_nature_query.validate("32 Jolly")
        self.assertEqual(res_both.result, AnswerType.CORRECT)

        res_wrong_nature = prompt_with_nature_query.validate("32 Adamant")
        # 32 Adamant reaches 154, not 169
        self.assertEqual(res_wrong_nature.result, AnswerType.INCORRECT)

    def test_metagame_prompts(self):
        earthquake = self.moves_db.name("Earthquake")
        dragon_claw = self.moves_db.name("Dragon Claw")

        mock_top_set = TopSet(
            entry=UsageEntry(pokemon=self.garchomp, rank=1, usage_percent=0.25, source="Test"),
            sets=CommonSets(
                pokemon=self.garchomp,
                moves=[
                    MoveUsage(move=earthquake, percent=0.95),
                    MoveUsage(move=dragon_claw, percent=0.70),
                ],
                items=[
                    ItemUsage(item=Item(name="Choice Scarf"), percent=0.60),
                    ItemUsage(item=Item(name="Life Orb"), percent=0.30),
                ],
                abilities=[
                    AbilityUsage(ability=Ability(name="Rough Skin"), percent=0.98),
                    AbilityUsage(ability=Ability(name="Sand Veil"), percent=0.02),
                ],
                natures=[
                    NatureUsage(nature=Nature.JOLLY, percent=0.80),
                    NatureUsage(nature=Nature.ADAMANT, percent=0.15),
                ],
                spreads=[],
                teammates=[],
                source="Test",
            ),
        )

        # Top Move Prompt
        move_prompt = TopMovePrompt(top_set=mock_top_set)
        self.assertEqual(move_prompt.validate("Earthquake").result, AnswerType.CORRECT)
        self.assertEqual(move_prompt.validate("earthquake").result, AnswerType.CORRECT)
        self.assertEqual(move_prompt.validate("Dragon Claw").result, AnswerType.PARTIAL)
        self.assertEqual(move_prompt.validate("Splash").result, AnswerType.INCORRECT)

        # Top Item Prompt
        item_prompt = TopItemPrompt(top_set=mock_top_set)
        self.assertEqual(item_prompt.validate("Choice Scarf").result, AnswerType.CORRECT)
        self.assertEqual(item_prompt.validate("choicescarf").result, AnswerType.CORRECT)
        self.assertEqual(item_prompt.validate("Life Orb").result, AnswerType.PARTIAL)
        self.assertEqual(item_prompt.validate("Leftovers").result, AnswerType.INCORRECT)

        # Top Ability Prompt
        ability_prompt = TopAbilityPrompt(top_set=mock_top_set)
        self.assertEqual(ability_prompt.validate("Rough Skin").result, AnswerType.CORRECT)
        self.assertEqual(ability_prompt.validate("roughskin").result, AnswerType.CORRECT)
        self.assertEqual(ability_prompt.validate("Sand Veil").result, AnswerType.PARTIAL)
        self.assertEqual(ability_prompt.validate("Intimidate").result, AnswerType.INCORRECT)

        # Top Nature Prompt
        nature_prompt = TopNaturePrompt(top_set=mock_top_set)
        self.assertEqual(nature_prompt.validate("Jolly").result, AnswerType.CORRECT)
        self.assertEqual(nature_prompt.validate("Adamant").result, AnswerType.PARTIAL)
        self.assertEqual(nature_prompt.validate("Modest").result, AnswerType.INCORRECT)

    def test_damage_calc_prompts_and_inferences(self):
        # Test weather and terrain inference
        drought = Ability(name="Drought")
        grassy_surge = Ability(name="Grassy Surge")

        self.assertEqual(infer_weather(drought, None), Weather.SUN)
        self.assertEqual(infer_terrain(grassy_surge, None), Terrain.GRASSY)
        self.assertEqual(infer_weather(None, None), Weather.NONE)
        self.assertEqual(infer_terrain(None, None), Terrain.NONE)

        # Build calculation scenario
        eq = self.moves_db.name("Earthquake")
        p1 = Pokemon(
            data=self.garchomp,
            moveset=MoveSet(moves=[eq]),
            typing=self.garchomp.typing,
            ability=list(self.garchomp.abilities)[0],
            item=None,
            gender=None,
            stats=Stats.of(
                base=self.garchomp.stats,
                evs=[EV(stat=Stat.ATTACK, number=StatPoint(number=32))],
                ivs=(),
                nature=Nature.JOLLY,
                level=50,
            ),
        )
        p2 = Pokemon(
            data=self.garchomp,
            moveset=MoveSet(moves=[eq]),
            typing=self.garchomp.typing,
            ability=list(self.garchomp.abilities)[0],
            item=None,
            gender=None,
            stats=Stats.of(
                base=self.garchomp.stats,
                evs=[EV(stat=Stat.HP, number=StatPoint(number=0))],
                ivs=(),
                nature=Nature.JOLLY,
                level=50,
            ),
        )

        s1 = PokemonState.fresh(p1, 0, 0)
        s2 = PokemonState.fresh(p2, 1, 0)
        board = BoardState(entities=[s1, s2])
        report = calculate_damage(s1, s2, eq, board)

        # Damage Range Prompt
        range_prompt = DamageRangePrompt(
            attacker=s1,
            defender=s2,
            move=eq,
            board_state=board,
            report=report,
        )
        prompt_str = range_prompt.get_prompt()
        self.assertIn("Garchomp", prompt_str)
        self.assertIn("Earthquake", prompt_str)

        # Rolls: 67-79 (36.6% - 43.1%)
        self.assertEqual(range_prompt.validate("36.6-43.1%").result, AnswerType.CORRECT)
        self.assertEqual(range_prompt.validate("40%").result, AnswerType.CORRECT)
        self.assertEqual(range_prompt.validate("38%").result, AnswerType.CORRECT)
        self.assertEqual(range_prompt.validate("67-79").result, AnswerType.CORRECT)
        self.assertEqual(range_prompt.validate("25%").result, AnswerType.PARTIAL)
        self.assertEqual(range_prompt.validate("90%").result, AnswerType.INCORRECT)

        # Knockout Prognosis Prompt
        ko_prompt = KnockoutPrognosisPrompt(
            attacker=s1,
            defender=s2,
            move=eq,
            board_state=board,
            report=report,
        )
        # 36.6-43.1% is a guaranteed 3HKO (3 hits)
        self.assertEqual(ko_prompt.validate("3").result, AnswerType.CORRECT)
        self.assertEqual(ko_prompt.validate("3hko").result, AnswerType.CORRECT)
        self.assertEqual(ko_prompt.validate("2-3").result, AnswerType.CORRECT)
        self.assertEqual(ko_prompt.validate("2").result, AnswerType.PARTIAL)  # off by 1
        self.assertEqual(ko_prompt.validate("5").result, AnswerType.INCORRECT)

    def test_quiz_score_rendering(self):
        quiz = BaseStatsQuiz(pokemon_pool=[self.garchomp], question_count=2)
        p1 = next(quiz)
        quiz.set_result(p1.validate("102"))
        p2 = next(quiz)
        quiz.set_result(p2.validate("100"))

        score_text = quiz.render_score()
        self.assertIn("Base Stats Quiz Results", score_text)
        self.assertIn("Total Questions : 2", score_text)
        self.assertIn("Final Score", score_text)

    def test_prompt_correct_answers_and_mega_filtering(self):
        # Test get_correct_answer on various prompts
        exact_p = ExactBaseStatPrompt(pokemon=self.garchomp, stat=Stat.SPEED)
        self.assertIn("102", exact_p.get_correct_answer())

        comp_p = CompareBaseStatPrompt(pokemon1=self.garchomp, pokemon2=self.salamence, stat=Stat.SPEED)
        self.assertIn(">", comp_p.get_correct_answer())

        same_p = SameBaseStatPrompt(pokemon=self.garchomp, stat=Stat.SPEED, target_value=102)
        self.assertIn("102", same_p.get_correct_answer())

        # Test Mega stone handling in TopItemPrompt
        charizard = list(self.db.name("Charizard"))[0]
        mega_charizard_set = TopSet(
            entry=UsageEntry(pokemon=charizard, rank=1, usage_percent=0.25, source="Test"),
            sets=CommonSets(
                pokemon=charizard,
                moves=[],
                items=[
                    ItemUsage(item=Item(name="Charizardite Y"), percent=0.70),
                    ItemUsage(item=Item(name="Choice Specs"), percent=0.20),
                    ItemUsage(item=Item(name="Life Orb"), percent=0.10),
                ],
                abilities=[],
                natures=[],
                spreads=[],
                teammates=[],
                source="Test",
            ),
        )
        item_prompt = TopItemPrompt(top_set=mega_charizard_set)
        # Should ask for non-Mega held item
        self.assertIn("non-Mega held item", item_prompt.get_prompt())
        # The correct answer should be Choice Specs (filtering out Charizardite Y)
        self.assertEqual(item_prompt.validate("Choice Specs").result, AnswerType.CORRECT)
        self.assertIn("Choice Specs", item_prompt.get_correct_answer())

    def test_allowed_prompt_types(self):
        # Base stats quiz with only exact prompts
        bs_quiz = BaseStatsQuiz(
            pokemon_pool=[self.garchomp],
            question_count=3,
            allowed_prompt_types=["exact"],
        )
        for p in bs_quiz:
            self.assertIsInstance(p, ExactBaseStatPrompt)

        # Metagame quiz with only move prompts
        eq = self.moves_db.name("Earthquake")
        mock_set = TopSet(
            entry=UsageEntry(pokemon=self.garchomp, rank=1, usage_percent=0.25, source="Test"),
            sets=CommonSets(
                pokemon=self.garchomp,
                moves=[MoveUsage(move=eq, percent=0.95)],
                items=[],
                abilities=[],
                natures=[],
                spreads=[],
                teammates=[],
                source="Test",
            ),
        )
        mg_quiz = MetagameQuiz(
            top_sets=[mock_set],
            question_count=3,
            allowed_prompt_types=["move"],
        )
        for p in mg_quiz:
            self.assertIsInstance(p, TopMovePrompt)

        # Damage calc quiz with only range prompts
        eq_move = self.moves_db.name("Earthquake")
        p1 = Pokemon(
            data=self.garchomp,
            moveset=MoveSet(moves=[eq_move]),
            typing=self.garchomp.typing,
            ability=list(self.garchomp.abilities)[0],
            item=None,
            gender=None,
            stats=Stats.of(
                base=self.garchomp.stats,
                evs=[EV(stat=Stat.ATTACK, number=StatPoint(number=32))],
                ivs=(),
                nature=Nature.JOLLY,
                level=50,
            ),
        )
        calc_quiz = DamageCalcQuiz(
            top_sets=[mock_set],
            question_count=2,
            allowed_prompt_types=["range"],
        )
        for p in calc_quiz:
            self.assertIsInstance(p, DamageRangePrompt)

    def test_unlikely_scenario_filtering(self):
        eq = self.moves_db.name("Earthquake")
        flamethrower = self.moves_db.name("Flamethrower")
        shadow_ball = self.moves_db.name("Shadow Ball")

        # Garchomp: Physical attacker (130 Atk / 80 SpA, Jolly nature, 32 Atk EVs)
        garchomp_phys = Pokemon(
            data=self.garchomp,
            moveset=MoveSet(moves=[eq, flamethrower]),
            typing=self.garchomp.typing,
            ability=list(self.garchomp.abilities)[0],
            item=None,
            gender=None,
            stats=Stats.of(
                base=self.garchomp.stats,
                evs=[EV(stat=Stat.ATTACK, number=StatPoint(number=32))],
                ivs=(),
                nature=Nature.JOLLY,
                level=50,
            ),
        )

        # Earthquake is likely, Flamethrower is unlikely
        self.assertTrue(is_likely_attacker_move(garchomp_phys, eq))
        self.assertFalse(is_likely_attacker_move(garchomp_phys, flamethrower))

        # Modest Garchomp with 32 SpA EVs using Earthquake
        garchomp_spec = Pokemon(
            data=self.garchomp,
            moveset=MoveSet(moves=[eq, flamethrower]),
            typing=self.garchomp.typing,
            ability=list(self.garchomp.abilities)[0],
            item=None,
            gender=None,
            stats=Stats.of(
                base=self.garchomp.stats,
                evs=[EV(stat=Stat.SP_ATTACK, number=StatPoint(number=32))],
                ivs=(),
                nature=Nature.MODEST,
                level=50,
            ),
        )
        # Modest hinders Attack and invests in SpA -> Earthquake is unlikely
        self.assertFalse(is_likely_attacker_move(garchomp_spec, eq))

        # State with Swords Dance (+2 Attack) using a special move
        garchomp_state = PokemonState.fresh(garchomp_phys, team=0, slot=0)
        garchomp_state.stats.add_modifiers(StatModifier(stat=Stat.ATTACK, modifier=2))
        self.assertTrue(is_likely_attacker_move(garchomp_state, eq))
        self.assertFalse(is_likely_attacker_move(garchomp_state, flamethrower))


if __name__ == "__main__":
    unittest.main()
