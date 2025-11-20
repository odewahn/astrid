import asyncio
import argparse


from rich import print
from rich.console import Console
from art import text2art

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

from typing import Optional, List
from openai.types.chat import ChatCompletionToolParam

from litellm import acompletion, stream_chunk_builder
from fastmcp import Client


# Turn off Pydantic deprecation warnings that happen with fastmcp
import warnings
from pydantic import PydanticDeprecatedSince20, PydanticDeprecatedSince211

warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince211)


# **********************************************************************
# UI class for managing status and token printing
# **********************************************************************
class TurnUI:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.status = console.status("")

    def set_status(self, text: str) -> None:
        self.status.start()
        self.status.update(text)

    def hide_status(self) -> None:
        self.status.stop()

    def print_streaming_token(self, text: str) -> None:
        self.console.print(text, end="", soft_wrap=True)

    def print(self, text: str) -> None:
        self.console.print(text)


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


# **********************************************************************
# Core turn completion logic
# **********************************************************************
async def complete_turn(
    initial_turn: Turn,
    config: dict = None,
    client: Client = None,
    tools: Optional[List[ChatCompletionToolParam]] = None,
    ui: Optional[TurnUI] = None,
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
        # `assistant_msg` may be a dict-like or Pydantic model; handle both.

        has_tool_calls = getattr(assistant_msg, "tool_calls", None)

        # No tool calls -> we are done
        if not has_tool_calls:
            break

        # Safety: if we can't actually run tools, just stop here
        if client is None:
            # Optional: you could add a system/assistant warning here instead
            break

        # Looped too many times? -> we are done
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
            args = safe_json_loads(tc["function"]["arguments"])

            if ui:
                ui.set_status(f"Running tool '{name}'...")

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


# **********************************************************************
# REPL Related Code
# **********************************************************************


async def get_input(session: PromptSession) -> str:
    with patch_stdout(session):
        try:
            text = await session.prompt_async()
            return text
        except KeyboardInterrupt:
            return "/quit"


async def run_repl(config: dict = None, client: Client = None, ui: TurnUI = None):

    # Print the startup screen
    Art = text2art(settings.ASSISTANT_NAME)
    ui.print(f"[bold green] {settings.ASSISTANT_NAME} client v{settings.VERSION}.")
    ui.print(f"[green]\n{Art}\n")

    session = PromptSession("> ")

    async with client:
        mcp_tools = await client.list_tools()
        openai_tools = convert_mcp_tools_to_openai_format(mcp_tools)
        while True:
            user_input = await get_input(session)

            if user_input in ["/exit", "/quit", "/q"]:
                break

            if user_input == "/config":
                ui.print(f"[bold blue]Current config file:[/bold blue] {config}")
                continue

            initial_turn = create_initial_turn(config, user_input)
            await complete_turn(
                initial_turn=initial_turn,
                config=config,
                client=client,
                tools=openai_tools,
                ui=ui,
            )
            ui.print("\n")


def main():
    console = Console()
    ui = TurnUI(console)
    parser = create_parser()
    args = parser.parse_args()
    print("Args", args)

    if args.version:
        print(f"{settings.ASSISTANT_NAME} version {settings.version}")
        return

    config = load_config(args.config)

    client = Client(config)

    asyncio.run(run_repl(config=config, client=client, ui=ui))
