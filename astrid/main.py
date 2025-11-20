import asyncio
import argparse

from astrid.settings import settings

from rich import print
from rich.console import Console
from art import text2art

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from astrid.utils import load_config


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{settings.ASSISTANT_NAME} - An AI Assistant Client"
    )
    parser.add_argument(
        "--version",
        "-v",
        action="store_true",
        help="Print the version and exit",
    )

    parser.add_argument(
        "--config",
        "-c",
        default=settings.config_file,
        help=(f"Path to config file"),
    )
    return parser


# Read the user input.  Set the quit_repl flag to True on EOF or KeyboardInterrupt.
async def get_input(session: PromptSession) -> str:
    with patch_stdout(session):
        try:
            text = await session.prompt_async()
            return text
        except KeyboardInterrupt:
            return "/quit"


async def run_repl(console: Console, config: dict = None):

    # Print the startup screen
    Art = text2art(settings.ASSISTANT_NAME)
    console.print(f"[bold green] {settings.ASSISTANT_NAME} client v{settings.version}.")
    console.print(f"[green]\n{Art}\n")

    session = PromptSession("> ")
    while True:
        user_input = await get_input(session)

        if user_input in ["/exit", "/quit", "/q"]:
            break

        if user_input == "/config":
            console.print(f"[bold blue]Current config file:[/bold blue] {config}")
            continue

        console.print(f"[bold blue]You entered:[/bold blue] {user_input}")


def main():
    console = Console()
    parser = create_parser()
    args = parser.parse_args()
    print("Args", args)

    if args.version:
        print(f"{settings.ASSISTANT_NAME} version {settings.version}")
        return

    config = load_config(args.config)

    asyncio.run(run_repl(console, config=config))
