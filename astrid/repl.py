from astrid.context import Context
from astrid.config import settings
from rich import print
from art import text2art

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.patch_stdout import patch_stdout


from rich.console import Console

console = Console()


class REPL:

    prompt: str = ">> "
    quit_repl: str = False

    session = PromptSession(ANSI(f"\n\033[1;32m{prompt}\033[0m"))

    def __init__(self, ctx: Context):
        self.ctx = ctx

    # Print the welcome message with ASCII art
    def print_welcome(self):
        Art = text2art(settings.ASSISTANT_NAME)
        print(f"[bold green] {settings.ASSISTANT_NAME} client v{settings.version}.")
        print(f"[green]\n{Art}\n")

    # Read the user input.  Set the quit_repl flag to True on EOF or KeyboardInterrupt.
    async def get_input(self) -> str:
        with patch_stdout():
            try:
                text = await self.session.prompt_async()
                # see if they've quit or exited
                if text in ["exit", "quit", "q"]:
                    self.quit_repl = True
                return text
            except (EOFError, KeyboardInterrupt):
                self.quit_repl = True

    def should_exit(self) -> bool:
        return self.quit_repl
