import asyncio
import argparse

from art import text2art
from rich import print
from rich.panel import Panel
from rich.console import Console

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from astrid.settings import settings
from astrid.utils import (
    load_config,
    convert_mcp_tools_to_openai_format,
    safe_json_loads,
    run_tool,
)
from astrid.conversation import Turn
from astrid.llm_ui import REPLTurnUI

from prompt_toolkit.formatted_text import HTML
from astrid.llm_ui import REPLTurnUI, print_credentials

from typing import Optional, List
from openai.types.chat import ChatCompletionToolParam

from litellm import acompletion, stream_chunk_builder
from fastmcp import Client


# Turn off Pydantic deprecation warnings that happen with fastmcp
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)


# **********************************************************************
# Set up the argument parser
# **********************************************************************


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
        default=settings.DEFAULT_CONFIG_FILE,
        help=(f"Path to config file"),
    )
    return parser


async def complete_turn(
    initial_turn: Turn,
    config: dict = None,
    client: Client = None,
    tools: Optional[List[ChatCompletionToolParam]] = None,
    ui: Optional[REPLTurnUI] = None,
    max_tool_loops: int = 4,
):

    # Create a copy of the turn to avoid mutating the original
    new_turn = initial_turn.model_copy(deep=True)

    if ui:
        ui.hide_status()

    while True:

        messages = [step.message for step in new_turn.steps]

        if ui:
            ui.set_status("Generating response...")

        stream = await acompletion(
            model=config.get("model", settings.DEFAULT_MODEL),
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            stream=True,
        )

        if ui:
            ui.hide_status()

        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
            delta = chunk.choices[0].delta
            # Print the streaming content tokens it arrives
            if ui and delta.content:
                ui.print_streaming_token(delta.content)

        # Collapse all chunks into a final response
        final = stream_chunk_builder(chunks)
        assistant_msg = final.choices[0].message

        # Record assistant step in the turn
        new_turn.add_raw(assistant_msg, usage=final.usage)

        # =====================================================================
        # 2. Check for tool calls
        # =====================================================================

        has_tool_calls = getattr(assistant_msg, "tool_calls", None)

        # No tool calls -> we are done
        if client is None or not has_tool_calls:
            break

        # Looped too many times -> we are done
        if new_turn.loop_count >= max_tool_loops:
            break

        new_turn.loop_count += 1

        # =====================================================================
        # 3. Execute each tool call via FastMCP client
        # =====================================================================
        tool_calls = (
            assistant_msg.model_dump()
            if hasattr(assistant_msg, "model_dump")
            else assistant_msg
        )

        # Call the tools and add them to the growing conversation for inclusion in the next iteration
        for tc in tool_calls["tool_calls"]:
            name = tc["function"]["name"]
            arg_str = tc["function"]["arguments"]
            args = safe_json_loads(arg_str)

            if ui:
                ui.set_status(f"Running '{name}' with {arg_str[:20]}...")

            result = await run_tool(client, name, args)

            if ui:
                ui.hide_status()

            new_turn.add_tool(
                tool_call_id=tc["id"],
                name=name,
                content=result,
            )

    return new_turn


def create_initial_turn(config, user_input: str) -> "Turn":
    turn = Turn()
    turn.add_system(config.get("system_prompt", settings.DEFAULT_SYSTEM_PROMPT))
    turn.add_user(user_input)
    return turn


async def run_repl(
    config: dict, client: Client, tools: List[ChatCompletionToolParam]
) -> None:
    console = Console()

    # Shared status for bottom toolbar
    status = {"text": ""}

    def set_status(text: str) -> None:
        status["text"] = text or ""

    def bottom_toolbar() -> str:
        base = "/help /config /creds /exit"
        if status["text"]:
            return f"{config.title} | {status['text']}"
        return base

    prompt_message = HTML(f"<ansigreen>{settings.ASSISTANT_NAME}&gt; </ansigreen>")
    session = PromptSession(
        prompt_message,
        bottom_toolbar=bottom_toolbar,
    )

    ui = REPLTurnUI(set_status_callback=set_status)

    console.print(
        "[bold]Type[/] [yellow]/help[/] [bold]for help,[/] "
        "[yellow]/config[/] [bold]for config,[/] "
        "[yellow]/creds[/] [bold]for console credentials,[/] "
        "[yellow]/exit[/] [bold]to quit.[/]\n"
    )

    while True:
        try:
            with patch_stdout():
                user_input = await session.prompt_async()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Exiting.[/]")
            break

        if user_input is None:
            continue

        text = user_input.strip()
        if not text:
            continue

        # REPL commands handled right here
        if text in ("/exit", "/quit"):
            console.print("[bold red]Goodbye.[/]")
            break

        if text == "/config":
            ui.print(f"Current config: {config}")
            continue

        if text == "/creds":
            print_credentials(console=console)
            continue

        if text == "/help":
            console.print(
                Panel(
                    "\n".join(
                        [
                            "/help   - show this help",
                            "/config - show current config",
                            "/creds  - show console login info",
                            "/exit   - quit the REPL",
                        ]
                    ),
                    title="Commands",
                    border_style="cyan",
                )
            )
            continue

        # Normal user input -> build a Turn and call complete_turn directly
        initial_turn = create_initial_turn(config, text)

        await complete_turn(
            initial_turn=initial_turn,
            config=config,
            client=client,
            tools=tools,
            ui=ui,
        )

        # Separate turns with a blank line
        import sys as _sys

        _sys.stdout.write("\n")
        _sys.stdout.flush()


def main():
    parser = create_parser()
    args = parser.parse_args()
    console = Console()

    if args.version:
        print(f"{settings.ASSISTANT_NAME} version {settings.VERSION}")
        return

    Art = text2art(settings.ASSISTANT_NAME, font="slant")
    console.print(f"[green]{Art}[/green]")
    console.print(f"{settings.ASSISTANT_NAME} version {settings.VERSION}")
    console.print("\n")

    config = load_config(args.config)

    # Print initial credentials hint (optional)
    from astrid.llm_ui import print_credentials

    print_credentials(console=console)

    async def runner():
        client = Client(config)

        async with client:
            # Fetch MCP tools once and convert to OpenAI format
            mcp_tools = await client.list_tools()
            tools = convert_mcp_tools_to_openai_format(mcp_tools)

            await run_repl(config=config, client=client, tools=tools)

    asyncio.run(runner())
