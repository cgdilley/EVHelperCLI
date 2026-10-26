import sys
import argparse

from EVHelperCLI.CLI.Quiz import main as quiz_main, add_quiz_arguments


def main(argv: list[str] | None = None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="EVHelper",
        description="EVHelper Command Line Interface",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    quiz_parser = subparsers.add_parser("quiz", help="Run Pokémon memorization quizzes")
    add_quiz_arguments(quiz_parser)

    if argv and argv[0] == "quiz":
        # Pass remaining arguments to quiz_main
        quiz_main(argv[1:])
        return

    # If no arguments or other subcommands
    args = parser.parse_args(argv)
    if args.subcommand == "quiz":
        quiz_main(argv[1:])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
