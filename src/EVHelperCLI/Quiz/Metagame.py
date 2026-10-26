import random
from abc import ABC
from typing import Sequence

from EVHelperCLI.Quiz.Common import RankedChoicePrompt
from EVHelperCLI.Quiz.Quiz import NumberedQuiz, Style, colorize
from EVHelperCLI.Data.Provider import UsageDataProvider
from EVHelperCLI.Data.Usage import TopSet


class MetagameQuizPrompt(RankedChoicePrompt, ABC):
    top_set: TopSet


class TopMovePrompt(MetagameQuizPrompt):
    LABEL = "moves"
    TOP_DISPLAY = 4
    PARTIAL_END = 5
    PARTIAL_BOUNDS = (0.4, 0.85)

    def get_prompt(self) -> str:
        pkmn_name = self.top_set.entry.pokemon.name
        return (
            f"{colorize('What is the most common move used by', Style.BOLD)} "
            f"{colorize(pkmn_name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        )

    def _entries(self):
        return self.top_set.sets.moves

    def _name_of(self, entry) -> str:
        return entry.move.name


def is_mega_stone(item_name: str) -> bool:
    low = item_name.lower()
    return low.endswith("ite") or low.endswith("ite x") or low.endswith("ite y") or low.endswith("ite z") or "blue orb" in low or "red orb" in low


class TopItemPrompt(MetagameQuizPrompt):
    LABEL = "items"
    TOP_DISPLAY = 4
    PARTIAL_END = 4
    PARTIAL_BOUNDS = (0.3, 0.75)

    def get_prompt(self) -> str:
        pkmn_name = self.top_set.entry.pokemon.name
        # Check if this Pokémon frequently holds a mega stone in its sets
        has_mega_stone = any(
            it.item and is_mega_stone(str(it.item.name))
            for it in self.top_set.sets.items
        )
        if has_mega_stone:
            return (
                f"{colorize('What is the most popular non-Mega held item for', Style.BOLD)} "
                f"{colorize(pkmn_name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
            )
        return (
            f"{colorize('What is the most popular held item for', Style.BOLD)} "
            f"{colorize(pkmn_name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        )

    def _entries(self):
        # Filter out Mega stones
        return [it for it in self.top_set.sets.items if it.item and not is_mega_stone(str(it.item.name))]

    def _name_of(self, entry) -> str:
        return entry.item.name


class TopAbilityPrompt(MetagameQuizPrompt):
    LABEL = "abilities"
    TOP_DISPLAY = 3
    PARTIAL_END = None
    PARTIAL_BOUNDS = (0.25, 0.7)

    def get_prompt(self) -> str:
        pkmn_name = self.top_set.entry.pokemon.name
        return (
            f"{colorize('What is the primary/most common competitive ability for', Style.BOLD)} "
            f"{colorize(pkmn_name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        )

    def _entries(self):
        return self.top_set.sets.abilities

    def _name_of(self, entry) -> str:
        return entry.ability.name


class TopNaturePrompt(MetagameQuizPrompt):
    LABEL = "natures"
    TOP_DISPLAY = 3
    PARTIAL_END = 4
    PARTIAL_BOUNDS = (0.3, 0.75)

    def get_prompt(self) -> str:
        pkmn_name = self.top_set.entry.pokemon.name
        return (
            f"{colorize('What is the most popular competitive nature for', Style.BOLD)} "
            f"{colorize(pkmn_name.name, Style.BOLD, Style.YELLOW)}{colorize('?', Style.BOLD)}"
        )

    def _entries(self):
        return self.top_set.sets.natures

    def _name_of(self, entry) -> str:
        return entry.nature.name


class MetagameQuiz(NumberedQuiz[MetagameQuizPrompt]):

    PROMPT_TYPES = {
        "move": TopMovePrompt,
        "item": TopItemPrompt,
        "ability": TopAbilityPrompt,
        "nature": TopNaturePrompt,
    }
    TITLE = "Metagame Quiz Results"
    TITLE_INDENT = 10

    def __init__(
        self,
        top_sets: Sequence[TopSet] | None = None,
        question_count: int = 10,
        allowed_prompt_types: Sequence[str] | None = None,
        inp=None,
        outp=None,
    ):
        super().__init__(
            question_count=question_count,
            allowed_prompt_types=allowed_prompt_types,
            inp=inp,
            outp=outp,
        )
        if top_sets is not None:
            self.top_sets = list(top_sets)
        else:
            provider = UsageDataProvider()
            self.top_sets = provider.top_common_sets(limit=50)

    def _pool_for(self, prompt_type: str) -> list[TopSet]:
        if prompt_type == "item":
            # Do not quiz Mega Pokémon forms for held items (their only item is the mega stone)
            eligible_sets = [s for s in self.top_sets if "Mega" not in str(s.entry.pokemon.name)]
            return eligible_sets or self.top_sets
        return self.top_sets

    def _generate_prompt(self) -> MetagameQuizPrompt:
        prompt_type = random.choice(self.allowed_prompt_types)
        top_set = random.choice(self._pool_for(prompt_type))
        return self.PROMPT_TYPES[prompt_type](top_set=top_set)
