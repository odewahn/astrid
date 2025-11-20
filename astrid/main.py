import asyncio

from astrid.config import settings

from rich import print
from rich.console import Console
from art import text2art

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout


# Read the user input.  Set the quit_repl flag to True on EOF or KeyboardInterrupt.
async def get_input(session: PromptSession) -> str:
    with patch_stdout(session):
        try:
            text = await session.prompt_async()
            return text
        except KeyboardInterrupt:
            return "/quit"


async def run_repl(console: Console):

    # Print the startup screen
    Art = text2art(settings.ASSISTANT_NAME)
    console.print(f"[bold green] {settings.ASSISTANT_NAME} client v{settings.version}.")
    console.print(f"[green]\n{Art}\n")

    session = PromptSession("> ")
    while True:
        user_input = await get_input(session)

        if user_input in ["/exit", "/quit", "/q"]:
            break

        console.print(f"[bold blue]You entered:[/bold blue] {user_input}")


def main():
    console = Console()
    asyncio.run(run_repl(console))
