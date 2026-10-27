
import os
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar, Iterator, Sequence
from datetime import datetime, UTC

from SprelfJSON import JSONModel


COLOR_ENABLED = "NO_COLOR" not in os.environ and sys.stdout.isatty()
if COLOR_ENABLED and os.name == "nt":
    os.system("")


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_RED = "\033[91m"


def colorize(text: str, *codes: str) -> str:
    if not COLOR_ENABLED or not codes:
        return text
    return "".join(codes) + text + Style.RESET


GRADE_STYLES: dict[str, tuple[str, ...]] = {
    "A": (Style.BOLD, Style.BRIGHT_GREEN),
    "B": (Style.BOLD, Style.GREEN),
    "C": (Style.BOLD, Style.YELLOW),
    "D": (Style.BOLD, Style.RED),
    "F": (Style.BOLD, Style.BRIGHT_RED),
}


class AnswerType(Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    SKIP = "skip"


class PromptResult(JSONModel):
    result: AnswerType
    answer: str
    value: float = 1

    @property
    def correct(self) -> bool:
        return self.result == AnswerType.CORRECT

    @classmethod
    def as_correct(cls, answer: str) -> "PromptResult":
        return cls(result=AnswerType.CORRECT, answer=answer, value=1.0)

    @classmethod
    def as_incorrect(cls, answer: str) -> "PromptResult":
        return cls(result=AnswerType.INCORRECT, answer=answer, value=0.0)

    @classmethod
    def as_partial(cls, answer: str, value: float) -> "PromptResult":
        return cls(result=AnswerType.PARTIAL, answer=answer, value=value)


def partial_credit(
    diff: float,
    max_error: float,
    exponent: float = 1.0,
    decimals: int = 3,
    scale: float | None = None,
) -> float | None:
    if diff > max_error:
        return None
    span = max_error if scale is None else scale
    return max(0.0, round((1.0 - (diff / span)) ** exponent, decimals))


def grade_for(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


class QuizPrompt(JSONModel, ABC):

    @abstractmethod
    def get_prompt(self) -> str:
        pass

    @abstractmethod
    def validate(self, answer: str) -> PromptResult:
        pass

    def get_correct_answer(self) -> str:
        return ""

    def get_feedback(self, result: PromptResult) -> str:
        if not result.correct:
            return self.get_correct_answer()
        return ""


TPrompt = TypeVar("TPrompt", bound=QuizPrompt)


class QuizHistory(JSONModel, Generic[TPrompt]):
    history: list[tuple[TPrompt, datetime, PromptResult]] = []

    def add(self, prompt: TPrompt, result: PromptResult, timestamp: datetime | None):
        timestamp = timestamp or datetime.now(tz=UTC)
        self.history.append((prompt, timestamp, result))

    def __len__(self) -> int:
        return len(self.history)

    def __iter__(self) -> Iterator[tuple[TPrompt, datetime, PromptResult]]:
        return iter(self.history)


class QuizOutput(ABC):

    @abstractmethod
    def render(self, text: str, **kwargs):
        pass


class QuizInput(ABC):
    @abstractmethod
    def collect(self, **kwargs) -> str:
        pass


class ConsoleOutput(QuizOutput):
    def render(self, text: str, **kwargs):
        print(text)


class ConsoleInput(QuizInput):
    def collect(self, reticle: str = "? ", **kwargs) -> str:
        answer = input(colorize(reticle, Style.BOLD, Style.BRIGHT_GREEN))
        if answer.lower() in ("quit", "exit"):
            raise StopIteration()
        return answer


class CompoundQuizOutput(QuizOutput):

    def __init__(self, *outputs: QuizOutput):
        self._outputs = outputs

    def render(self, text: str, **kwargs):
        for output in self._outputs:
            output.render(text, **kwargs)


#


class Quiz(Iterator[TPrompt], Generic[TPrompt], ABC):

    def __init__(self, inp: QuizInput | None = None, outp: QuizOutput | None = None):
        self._history: QuizHistory[TPrompt] = QuizHistory()
        self._current: TPrompt | None = None
        self._input: QuizInput = inp or ConsoleInput()
        self._output: QuizOutput = outp or ConsoleOutput()

    def __next__(self) -> TPrompt:
        n = self._get_next()
        if n is None:
            raise StopIteration()
        self._current = n
        return n

    @property
    def output(self) -> QuizOutput:
        return self._output

    @property
    def input(self) -> QuizInput:
        return self._input

    @abstractmethod
    def _get_next(self) -> TPrompt | None:
        ...

    def set_result(self, prompt: PromptResult, timestamp: datetime | None = None):
        if self._current is None:
            raise ValueError("No current prompt")
        self._history.add(self._current, prompt, timestamp=timestamp)
        self._current = None

    def prompt(self):
        try:
            self._prompt(next(self))
        except StopIteration:
            pass

    def run(self):
        for p in self:
            try:
                self._prompt(p)
            except (StopIteration, KeyboardInterrupt, EOFError):
                self._output.render("Exiting quiz early...")
                break
        self._output.render("\n" + self.render_score())

    def _prompt(self, p: TPrompt):
        self._output.render(p.get_prompt())
        answer = self._input.collect()
        result = p.validate(answer)
        self.set_result(result)

        if result.result == AnswerType.CORRECT:
            self._output.render(f"✓ Correct! (+{result.value:.1f} pts)")
        elif result.result == AnswerType.PARTIAL:
            self._output.render(f"~ Partial Credit! (+{result.value:.2f} pts)")
        else:
            self._output.render(f"✗ Incorrect (+0.0 pts)")

        feedback = p.get_feedback(result)
        if feedback:
            self._output.render(feedback)
        self._output.render("")

    def score(self) -> float:
        return sum(r.value for _, _, r in self._history) / len(self._history)

    @abstractmethod
    def render_score(self) -> str:
        ...


class NumberedQuiz(Quiz[TPrompt], ABC):

    PROMPT_TYPES: dict[str, type[TPrompt]] = {}
    DEFAULT_PROMPT_TYPES: Sequence[str] | None = None
    TITLE: str = ""
    TITLE_INDENT: int = 0

    def __init__(
        self,
        question_count: int = 10,
        allowed_prompt_types: Sequence[str] | None = None,
        inp=None,
        outp=None,
    ):
        super().__init__(inp=inp, outp=outp)
        self.question_count = question_count
        self.allowed_prompt_types = self._normalize_prompt_types(allowed_prompt_types)
        self._generated_count = 0

    @classmethod
    def _normalize_prompt_types(cls, allowed_prompt_types: Sequence[str] | None) -> list[str]:
        defaults = list(cls.DEFAULT_PROMPT_TYPES or cls.PROMPT_TYPES.keys())
        if allowed_prompt_types is None:
            return defaults
        selected = [t.lower() for t in allowed_prompt_types if t.lower() in cls.PROMPT_TYPES]
        return selected or defaults

    def _get_next(self) -> TPrompt | None:
        if self._generated_count >= self.question_count:
            return None
        self._generated_count += 1
        return self._generate_prompt()

    @abstractmethod
    def _generate_prompt(self) -> TPrompt:
        ...

    def _prompt(self, p: TPrompt):
        curr_pos = self._generated_count
        self.output.render(f"[Question {curr_pos}/{self.question_count}]")
        super()._prompt(p)

    def render_score(self) -> str:
        total = len(self._history)
        if total == 0:
            return "No questions answered."

        correct_count = sum(1 for _, _, r in self._history if r.result == AnswerType.CORRECT)
        partial_count = sum(1 for _, _, r in self._history if r.result == AnswerType.PARTIAL)
        incorrect_count = sum(1 for _, _, r in self._history if r.result == AnswerType.INCORRECT)
        score_val = self.score() * 100.0

        grade = grade_for(score_val)
        rule = colorize("=" * 40, Style.DIM)
        lines = [
            rule,
            colorize(f"{' ' * self.TITLE_INDENT}{self.TITLE}", Style.BOLD, Style.CYAN),
            rule,
            f"{colorize('Total Questions :', Style.DIM)} {colorize(str(total), Style.BOLD)}",
            f"{colorize('Correct         :', Style.DIM)} {colorize(str(correct_count), Style.GREEN)}",
            f"{colorize('Partial Credit  :', Style.DIM)} {colorize(str(partial_count), Style.YELLOW)}",
            f"{colorize('Incorrect       :', Style.DIM)} {colorize(str(incorrect_count), Style.RED)}",
            (
                f"{colorize('Final Score     :', Style.DIM)} "
                f"{colorize(f'{score_val:.1f}%', Style.BOLD)} "
                f"(Grade: {colorize(grade, *GRADE_STYLES[grade])})"
            ),
            rule,
        ]
        return "\n".join(lines)
