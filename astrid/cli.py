import json
import asyncio
from rich.console import Console
from astrid.config import settings
from astrid.context import Context
from astrid.llm_processor import LLMProcessor
from astrid.repl import REPL


async def run_repl(console: Console):
    ctx = Context()
    repl = REPL(ctx, console)
    llm = LLMProcessor(ctx, console)

    repl.print_welcome()
    while True:
        user_input = await repl.get_input()
        if repl.should_exit():
            console.print("[bold red]Exiting REPL. Goodbye![/bold red]")
            break

        ctx.append(user_input, "user")
        with console.status("Thinking..."):
            response = llm.process_mock(user_input, settings.DEFAULT_MODEL)
        ctx.append(response, "assistant")

        console.print(response, "\n", json.dumps(ctx.get_context(), indent=2))


def main():
    console = Console()
    asyncio.run(run_repl(console))
