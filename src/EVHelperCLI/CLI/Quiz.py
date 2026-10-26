import argparse
import sys
from dataclasses import dataclass

from EVHelperCLI.Quiz import (
    BaseStatsQuiz,
    MetagameQuiz,
    DamageCalcQuiz,
    AnswerType,
)


@dataclass(frozen=True)
class QuizEntry:
    key: str
    aliases: tuple[str, ...]
    title: str
    description: str
    quiz_class: type


QUIZZES = (
    QuizEntry("stats", ("base_stats",), "Base Stats Quiz", "Stats, Comparisons, Speed, EVs", BaseStatsQuiz),
    QuizEntry("meta", ("metagame",), "Metagame Quiz", "Common Moves, Items, Abilities, Natures", MetagameQuiz),
    QuizEntry("calc", ("calculations",), "Damage Calculations Quiz", "Damage Ranges, KO Thresholds", DamageCalcQuiz),
)

QUIZ_LOOKUP = {name: entry for entry in QUIZZES for name in (entry.key, *entry.aliases)}
QUIZ_CHOICES = [entry.key for entry in QUIZZES] + [alias for entry in QUIZZES for alias in entry.aliases]


def add_quiz_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-q",
        "--quiz",
        choices=QUIZ_CHOICES,
        help="Type of quiz to run: 'stats', 'meta', or 'calc'",
    )
    parser.add_argument(
        "-n",
        "--questions",
        type=int,
        default=10,
        help="Number of questions in the quiz (default: 10)",
    )
    parser.add_argument(
        "-p",
        "--prompts",
        "--prompt-types",
        nargs="+",
        default=None,
        help="Allowed prompt types for the chosen quiz (defaults to all)",
    )


def run_quiz_interactive(quiz, quiz_name: str = "Quiz"):
    print("\n" + "=" * 50)
    print(f"  Starting {quiz_name} ({quiz.question_count} questions)")
    print("  (Type 'quit' or 'exit' at any time to finish early)")
    print("=" * 50 + "\n")

    question_num = 0
    for prompt in quiz:
        question_num += 1
        print(f"[Question {question_num}/{quiz.question_count}]")
        print(prompt.get_prompt())
        try:
            answer = input("\nYour answer: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nQuiz interrupted.")
            break

        if answer.lower() in ("quit", "exit"):
            print("Exiting quiz early...")
            break

        result = prompt.validate(answer)
        quiz.set_result(result)

        if result.result == AnswerType.CORRECT:
            print(f"✓ Correct! (+{result.value:.1f} pts)")
        elif result.result == AnswerType.PARTIAL:
            print(f"~ Partial Credit! (+{result.value:.2f} pts)")
        else:
            print(f"✗ Incorrect (+0.0 pts)")

        feedback = prompt.get_feedback(result)
        if feedback:
            print(feedback)

        print()

    print("\n" + quiz.render_score())


def select_quiz_interactive() -> str:
    options = [str(index) for index in range(1, len(QUIZZES) + 2)]
    exit_option = options[-1]
    print("=" * 50)
    print("          EVHelper Pokémon Memorization Quizzes")
    print("=" * 50)
    for index, entry in enumerate(QUIZZES, start=1):
        print(f"{index}. {entry.title} ({entry.description})")
    print(f"{exit_option}. Exit")
    print("=" * 50)

    while True:
        try:
            choice = input(f"Select a quiz (1-{exit_option}): ").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

        for index, entry in enumerate(QUIZZES, start=1):
            if choice in (str(index), entry.key, *entry.aliases):
                return entry.key
        if choice in (exit_option, "exit", "quit"):
            print("Goodbye!")
            sys.exit(0)
        print(f"Invalid choice. Please enter {', '.join(options[:-1])}, or {exit_option}.")


def main(args_list: list[str] | None = None):
    parser = argparse.ArgumentParser(description="EVHelper Pokémon Memorization Quizzes")
    add_quiz_arguments(parser)

    args = parser.parse_args(args_list)

    chosen_quiz = args.quiz
    question_count = args.questions
    allowed_prompts = args.prompts

    if not chosen_quiz:
        chosen_quiz = select_quiz_interactive()

    entry = QUIZ_LOOKUP[chosen_quiz]
    quiz = entry.quiz_class(question_count=question_count, allowed_prompt_types=allowed_prompts)
    run_quiz_interactive(quiz, entry.title)


if __name__ == "__main__":
    main()
