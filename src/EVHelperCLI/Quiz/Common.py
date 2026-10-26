import re
from abc import ABC, abstractmethod
from typing import Any

from SprelfPkmn import Stat

from EVHelperCLI.Quiz.Quiz import QuizPrompt, PromptResult, Style, colorize


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_first_int(text: str) -> int | None:
    match = re.search(r"-?\d+", text.strip())
    return int(match.group(0)) if match else None


class RankedChoicePrompt(QuizPrompt, ABC):
    LABEL = ""
    TOP_DISPLAY = 3
    PARTIAL_END = None
    PARTIAL_BOUNDS = (0.0, 1.0)

    @abstractmethod
    def _entries(self) -> list[Any]:
        ...

    @abstractmethod
    def _name_of(self, entry: Any) -> str:
        ...

    def get_correct_answer(self) -> str:
        entries = self._entries()
        if not entries:
            return ""
        top = entries[0]
        others = [f"{self._name_of(e)} ({int((e.percent or 0) * 100)}%)" for e in entries[:self.TOP_DISPLAY]]
        return f"{self._name_of(top)} (Top {self.LABEL}: {', '.join(others)})"

    def validate(self, answer: str) -> PromptResult:
        norm_ans = normalize_name(answer)
        if not norm_ans:
            return PromptResult.as_incorrect(answer)

        entries = self._entries()
        if not entries:
            return PromptResult.as_incorrect(answer)

        top = entries[0]
        if norm_ans == normalize_name(self._name_of(top)):
            return PromptResult.as_correct(answer)

        low, high = self.PARTIAL_BOUNDS
        for e in entries[1:self.PARTIAL_END]:
            if norm_ans == normalize_name(self._name_of(e)):
                ratio = (e.percent or 0.1) / (top.percent or 1.0)
                return PromptResult.as_partial(answer, max(low, min(high, round(ratio, 2))))

        return PromptResult.as_incorrect(answer)


def format_stat_name(stat: Stat) -> str:
    if stat == Stat.SP_ATTACK:
        return "Special Attack"
    if stat == Stat.SP_DEFENSE:
        return "Special Defense"
    if stat == Stat.HP:
        return "HP"
    return stat.name.capitalize()


def short_stat_name(stat: Stat) -> str:
    if stat == Stat.SP_ATTACK:
        return "SpA"
    if stat == Stat.SP_DEFENSE:
        return "SpD"
    if stat == Stat.ATTACK:
        return "Atk"
    if stat == Stat.DEFENSE:
        return "Def"
    if stat == Stat.SPEED:
        return "Spe"
    if stat == Stat.HP:
        return "HP"
    return stat.name.capitalize()
