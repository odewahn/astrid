import asyncio
import argparse
import sys
import os

from rich.console import Console

console = Console()
from astrid.settings import settings

version_string = f"{settings.ASSISTANT_NAME} version {settings.VERSION}"

with console.status(f"Loading {version_string}..."):

    from art import text2art

    from prompt_toolkit import PromptSession
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.formatted_text import HTML

    from astrid.utils import (
        load_config,
        convert_mcp_tools_to_openai_format,
        safe_json_loads,
        run_tool,
        clone_repo,
        load_file,
        load_and_decrypt_env,
    )
    from astrid.conversation import Turn

    from astrid.llm_ui import REPLTurnUI, print_credentials, print_help

    from typing import Optional, List
    from openai.types.chat import ChatCompletionToolParam

    from litellm import acompletion, stream_chunk_builder
    from fastmcp import Client
    from fastmcp.exceptions import ToolError  # if not already imported
    import traceback


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
        default=None,
        help=(f"Path to config file"),
    )

    parser.add_argument(
        "--repo",
        "-r",
        default=None,
        help="URL of the git repository to clone",
    )
    parser.add_argument(
        "--dangerouslyInsecurePassword",
        action="store_true",
        help=(
            "Prompt for password to decrypt ENCRYPTED_ANTHROPIC_API_KEY "
            "and override the plaintext API key in memory"
        ),
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
                ui.set_status(f"Running '{name}' with {arg_str[:100]}...")

            try:
                result = await run_tool(client, name, args)
            except Exception as e:
                # Don’t crash the REPL – turn this into a tool “error result”
                if ui:
                    ui.hide_status()

                tb = traceback.format_exc()
                # You can make this as structured as you like; simple text works fine
                result = (
                    f"TOOL_ERROR: Tool '{name}' failed.\n"
                    f"Error: {e}\n"
                    f"Original arguments: {arg_str}\n"
                    f"Traceback:\n{tb}"
                )

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


from typing import Dict


async def run_repl(
    config: dict,
    client: Client,
    tools: List[ChatCompletionToolParam],
    ui: REPLTurnUI,
    status: Dict[str, str],
) -> None:
    console = Console()

    def bottom_toolbar() -> str:
        base = f"{config['title']} | /help /config /creds /exit"
        if status.get("text"):
            return f"{base} | {status['text']}"
        return base

    prompt_message = HTML(f"<ansigreen>{settings.ASSISTANT_NAME}&gt; </ansigreen>")
    session = PromptSession(
        prompt_message,
        bottom_toolbar=bottom_toolbar,
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
            print_help(console=console)
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

        sys.stdout.write("\n\n")
        sys.stdout.flush()


async def discover_all_tools(config):
    all_tools = []
    # config["mcpServers"] is a dict of {name: server_cfg}
    for name, server_cfg in config.get("mcpServers", {}).items():
        single_cfg = {"mcpServers": {name: server_cfg}}
        try:
            async with Client(single_cfg) as c:
                server_tools = await c.list_tools()
                # Optionally prefix names with the server name to avoid collisions
                for t in server_tools:
                    t.name = f"{name}_{t.name}"
                all_tools.extend(server_tools)
        except Exception as e:
            console.print(f"[red]Failed to list tools from server {name}: {e}[/red]")
    return all_tools


def main():
    Art = text2art(settings.ASSISTANT_NAME, font="slant")
    console.print(f"[green]{Art}[/green]")
    console.print(f"{settings.ASSISTANT_NAME} version {settings.VERSION}")
    console.print("\n")

    parser = create_parser()
    args = parser.parse_args()

    if args.version:
        print(version_string)
        return

    # ensure they've entered a config or a repo, but not both!
    if not args.config and not args.repo:
        console.print(
            "[red]Error: You must supply either a config file (--config) or a repository URL (--repo).[/red]"
        )
        return

    # If requested, decrypt the wrapped Anthropic key and override the plain var
    if args.dangerouslyInsecurePassword:
        try:
            decrypted = load_and_decrypt_env("ENCRYPTED_ANTHROPIC_API_KEY")
        except Exception as e:
            console.print(
                f"[bold red]Error unlocking ENCRYPTED_ANTHROPIC_API_KEY:[/] {e}"
            )
            raise SystemExit(1)

        os.environ["ANTHROPIC_API_KEY"] = decrypted

    # If they've supplied a repo URL, clone it to the content directory if it doesn't exist
    # Note that this needs to happen before loading the config, since the config may be in the repo
    # So, keep it before loading the config for the repo option
    if args.repo:
        try:
            clone_repo(args.repo, settings.REPO_CONTENT_DIR, overwrite=False)
            console.print(
                f"[green]Cloned repository from {args.repo} to {settings.REPO_CONTENT_DIR}[/green]"
            )
        except FileExistsError:
            console.print(
                f"[yellow]Directory {settings.REPO_CONTENT_DIR} already exists. Skipping clone.[/yellow]"
            )
        except Exception as e:
            console.print(f"[red]Failed to clone repository: {e}[/red]")
            return

    # If they've supplied a repo, then load the config from it and ask them which scenario they want to run
    if args.repo:
        config = load_config(settings.REPO_CONFIG_FILE)
        for i, content in enumerate(config.get("contents", [])):
            console.print(f"[{i}] {content.get('title', 'Untitled Scenario')}")
        choice = console.input("Select a scenario by number: ")
        try:
            choice_idx = int(choice)
            content_fn = config["contents"][choice_idx]["filename"]
            system_prompt = load_file(
                os.path.join(settings.REPO_CONTENT_DIR, content_fn)
            )
            config["system_prompt"] = system_prompt
        except (ValueError, IndexError):
            console.print(f"[red]Invalid selection '{choice}'. Exiting.[/red]")
            return

    if args.config:
        config = load_config(args.config)

    # Patch in any inherited shell variables from the environment

    inherited = config.get("inherited_shell_variables", []) or []
    for server_name, server_cfg in config.get("mcpServers", {}).items():
        # Preserve any existing env config
        env = server_cfg.setdefault("env", {})

        # Merge in inherited vars *without* overwriting existing keys
        for var in inherited:
            if var in os.environ and var not in env:
                env[var] = os.environ[var]

    # Begin the loop
    print_credentials(console=console)

    # ---- status + callback live here ----
    status = {"text": ""}

    def set_status(text: str) -> None:
        status["text"] = text or ""

    # UI is composed here and passed into run_repl
    ui = REPLTurnUI(set_status_callback=set_status)

    async def runner():
        client = Client(config)

        ui.set_status("Connecting to MCP server...")
        async with client:
            # Fetch MCP tools once and convert to OpenAI format
            # mcp_tools = await client.list_tools()
            mcp_tools = await discover_all_tools(config)
            tools = convert_mcp_tools_to_openai_format(mcp_tools)
            ui.hide_status()
            await run_repl(
                config=config,
                client=client,
                tools=tools,
                ui=ui,
                status=status,
            )

    asyncio.run(runner())
