import json
from rich.console import Console

console = Console()


import os
from astrid.repl import REPL

from astrid.config import settings
from astrid.context import Context
from astrid.llm_processor import LLMProcessor

import asyncio


async def main():
    ctx = Context()
    repl = REPL(ctx)
    llm_processor = LLMProcessor(ctx)
    repl.print_welcome()
    while True:
        user_input = await repl.get_input()
        if repl.should_exit():
            console.print("[bold red]Exiting REPL. Goodbye![/bold red]")
            break
        ctx.append(user_input, "user")
        response = llm_processor.process_mock(user_input, settings.DEFAULT_MODEL)
        ctx.append(response, "assistant")

        print(response, "\n", json.dumps(ctx.get_context(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
