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
    llm = LLMProcessor(console)

    repl.print_welcome()
    while True:
        user_input = await repl.get_input()
        if repl.should_exit():
            console.print("[bold red]Exiting REPL. Goodbye![/bold red]")
            break

        try:
            ctx.append(user_input, "user")
            response_chunks = []
            for chunk in llm.stream(ctx, settings.DEFAULT_MODEL):
                console.print(chunk, end="", soft_wrap=True)
                response_chunks.append(chunk)
            response = "".join(response_chunks)
            ctx.append(response, "assistant")
            console.print()
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")


def main():
    console = Console()
    asyncio.run(run_repl(console))
