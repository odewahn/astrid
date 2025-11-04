import json
from rich.console import Console

console = Console()


from astrid.repl import REPL
from astrid.config import settings
from astrid.context import Context
from astrid.llm_processor import LLMProcessor

import asyncio


async def _main_async():
    ctx = Context()
    repl = REPL(ctx, console)
    llm_processor = LLMProcessor(ctx, console)
    repl.print_welcome()
    while True:
        user_input = await repl.get_input()
        if repl.should_exit():
            console.print("[bold red]Exiting REPL. Goodbye![/bold red]")
            break
        ctx.append(user_input, "user")
        with console.status("Thinking..."):
            response = llm_processor.process_mock(user_input, settings.DEFAULT_MODEL)
        ctx.append(response, "assistant")

        console.print(response, "\n", json.dumps(ctx.get_context(), indent=2))


def main():
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
