#!/usr/bin/env python3
"""
Minimal, self-contained prompt_toolkit TUI demo with:

- Chat panel (streaming output)
- History panel
- Input at the bottom
- Fake "tools" support
- Simple Turn / complete_turn scaffolding

Run with:

    pip install prompt_toolkit
    python astrid_tui_demo.py
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style


# ============================================================
# Fake "settings" and config
# ============================================================


class Settings:
    ASSISTANT_NAME = "Astrid"
    VERSION = "0.0.1"
    DEFAULT_CONFIG_FILE = "config.yml"
    DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


settings = Settings()


# For this demo, config is just a dict; in your real app you'll load from file.
def load_config_dummy() -> Dict[str, Any]:
    return {
        "model": "demo-model",
        "system_prompt": settings.DEFAULT_SYSTEM_PROMPT,
    }


# ============================================================
# Minimal conversation model: Turn / Step
# (In your code, you already have astrid.conversation.Turn etc.)
# ============================================================


@dataclass
class Step:
    message: Dict[str, Any]
    usage: Optional[Dict[str, Any]] = None


@dataclass
class Turn:
    steps: List[Step] = field(default_factory=list)
    loop_count: int = 0

    def add_system(self, content: str):
        self.steps.append(Step({"role": "system", "content": content}))

    def add_user(self, content: str):
        self.steps.append(Step({"role": "user", "content": content}))

    def add_raw(self, message: Dict[str, Any], usage: Optional[Dict[str, Any]] = None):
        self.steps.append(Step(message, usage))

    def add_tool(self, tool_call_id: str, name: str, content: str):
        # For demo, just add a tool role message.
        self.steps.append(Step({"role": "tool", "name": name, "content": content}))


def create_initial_turn(config: dict, user_input: str) -> Turn:
    turn = Turn()
    turn.add_system(config.get("system_prompt", settings.DEFAULT_SYSTEM_PROMPT))
    turn.add_user(user_input)
    return turn


# ============================================================
# Fake tool client (to demonstrate tools)
# ============================================================


class DummyClient:
    """Simulated tool client with one tool: reverse(text=...)."""

    async def list_tools(self):
        # In your real code, FastMCP.Client.list_tools() returns real tools.
        return [{"name": "reverse", "description": "Reverse text"}]

    async def run_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "reverse":
            text = args.get("text", "")
            return text[::-1]
        return f"Unknown tool {name}"


# ============================================================
# UI Adapter: what complete_turn will call for streaming
# ============================================================


class PromptToolkitTurnUI:
    """
    UI object passed into complete_turn:

    - print_streaming_token: appends tokens to the chat TextArea
    - print: appends full lines to the chat TextArea
    - set_status/hide_status: currently no-op (could hook into a status bar)
    """

    def __init__(self, chat_output: TextArea, app: Application) -> None:
        self.chat_output = chat_output
        self.app = app

    def set_status(self, text: str) -> None:
        # Put status handling here if you want a status bar.
        # For now, do nothing.
        pass

    def hide_status(self) -> None:
        pass

    def _append_text(self, text: str) -> None:
        current = self.chat_output.text or ""
        self.chat_output.text = current + text
        self.chat_output.buffer.cursor_position = len(self.chat_output.text)
        self.app.invalidate()

    def print_streaming_token(self, text: str) -> None:
        # Streaming tokens get appended without newline
        self._append_text(text)

    def print(self, text: str) -> None:
        # Normal prints get a newline
        current = self.chat_output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self.chat_output.text = current + text + "\n"
        self.chat_output.buffer.cursor_position = len(self.chat_output.text)
        self.app.invalidate()


# ============================================================
# Demo complete_turn with streaming + tools
# (Replace this with your real complete_turn later.)
# ============================================================


async def complete_turn(
    initial_turn: Turn,
    config: dict,
    client: Optional[DummyClient] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    ui: Optional[PromptToolkitTurnUI] = None,
    max_tool_loops: int = 2,
) -> Turn:
    """
    Demo version of your complete_turn:

    - If user input starts with "/reverse", call the 'reverse' tool.
    - Otherwise, echo back a fake assistant reply.
    - Streams the assistant reply token-by-token via ui.print_streaming_token.
    """

    new_turn = initial_turn  # no deep copy needed for demo

    # Get the last user message:
    last_user_msg = ""
    for step in reversed(new_turn.steps):
        if step.message.get("role") == "user":
            last_user_msg = step.message.get("content", "")
            break

    # Tool case:
    if last_user_msg.startswith("/reverse") and client is not None:
        # Example: "/reverse hello world"
        parts = last_user_msg.split(" ", 1)
        text_to_reverse = parts[1] if len(parts) > 1 else ""
        if ui:
            ui.set_status("Running tool 'reverse'...")
        tool_result = await client.run_tool("reverse", {"text": text_to_reverse})
        if ui:
            ui.hide_status()
            ui.print(f"[tool reverse] {tool_result}")
        new_turn.add_tool("dummy-id", "reverse", tool_result)

        # Assistant acknowledges
        reply = f"The reversed text is: {tool_result}"

    else:
        # Normal assistant reply (for demo)
        reply = f"You said: {last_user_msg}. This is a demo streaming response."

    # Simulate streaming:
    if ui:
        for ch in reply:
            await asyncio.sleep(0.02)  # small delay for dramatization
            ui.print_streaming_token(ch)
        # Ensure we end the line
        ui.print("")

    # Record assistant step
    new_turn.add_raw({"role": "assistant", "content": reply}, usage=None)
    return new_turn


# ============================================================
# ChatUI using prompt_toolkit Application
# ============================================================


class ChatUI:
    """
    prompt_toolkit-based TUI:

    - Top: menu bar (text)
    - Left: chat log (streaming)
    - Right: history
    - Bottom: input line
    """

    def __init__(
        self,
        config: dict,
        client: Optional[DummyClient],
        tools: Optional[List[Dict[str, Any]]],
    ) -> None:
        self.config = config
        self.client = client
        self.tools = tools

        self.turn_counter = 0
        self.history: List[str] = []
        self.busy = False  # prevent overlapping turns

        # ----------------------------
        # Widgets
        # ----------------------------
        self.menu_bar = Window(
            height=1,
            content=FormattedTextControl(
                lambda: [
                    ("class:menu", f" {settings.ASSISTANT_NAME} TUI "),
                    ("", " | "),
                    ("class:menu-key", "F1"),
                    ("", ": Models "),
                    ("class:menu-key", "F2"),
                    ("", ": Config "),
                    ("class:menu-key", "F3"),
                    ("", ": Help "),
                    ("", " | Ctrl-C: Quit "),
                ]
            ),
        )

        self.chat_output = TextArea(
            text="",
            focusable=False,
            scrollbar=True,
            wrap_lines=True,
            read_only=True,
        )

        self.history_output = TextArea(
            text="",
            focusable=False,
            scrollbar=True,
            wrap_lines=False,
            read_only=True,
        )

        self.input_field = TextArea(
            height=1,
            prompt="> ",
            multiline=False,
        )

        # Accept handler for Enter in the input field
        self.input_field.accept_handler = self._on_enter

        chat_frame = Frame(self.chat_output, title="Conversation")
        history_frame = Frame(self.history_output, title="History")

        body = HSplit(
            [
                self.menu_bar,
                VSplit(
                    [
                        chat_frame,
                        history_frame,
                    ],
                    padding=1,
                ),
                self.input_field,
            ]
        )

        self.layout = Layout(body, focused_element=self.input_field)

        # ----------------------------
        # Key bindings
        # ----------------------------
        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            "Ctrl-C quits the app."
            event.app.exit()

        self.kb = kb

        # ----------------------------
        # Style
        # ----------------------------
        self.style = Style.from_dict(
            {
                "menu": "reverse",
                "menu-key": "bold underline",
                "frame.label": "bold",
            }
        )

        # ----------------------------
        # Application
        # ----------------------------
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            full_screen=True,
            style=self.style,
            mouse_support=True,
        )

        # Turn UI adapter that complete_turn will use for streaming
        self.turn_ui = PromptToolkitTurnUI(self.chat_output, self.app)

    # --------------------------------------------------
    # Helpers to update chat/history
    # --------------------------------------------------
    def append_chat_line(self, prefix: str, text: str) -> None:
        current = self.chat_output.text or ""
        line = f"[{prefix}] {text}"
        if current and not current.endswith("\n"):
            current += "\n"
        self.chat_output.text = current + line + "\n"
        self.chat_output.buffer.cursor_position = len(self.chat_output.text)
        self.app.invalidate()

    def append_history(self, line: str) -> None:
        current = self.history_output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self.history_output.text = current + line + "\n"
        self.history_output.buffer.cursor_position = len(self.history_output.text)
        self.app.invalidate()

    # --------------------------------------------------
    # Input handling
    # --------------------------------------------------
    def _on_enter(self, buff) -> bool:
        """
        Called when Enter is pressed in the input field.
        """
        if self.busy:
            self.append_chat_line(
                "System", "Busy; please wait for the current response."
            )
            return True

        user_text = self.input_field.text.strip()
        if not user_text:
            return True  # nothing to do

        # Clear input
        self.input_field.text = ""

        # Echo user text in chat and history
        self.turn_counter += 1
        self.append_chat_line("You", user_text)
        self.append_history(f"{self.turn_counter}: {user_text[:40]}")

        # Start assistant prefix for streaming
        current = self.chat_output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        self.chat_output.text = current + "[Assistant] "
        self.chat_output.buffer.cursor_position = len(self.chat_output.text)
        self.app.invalidate()

        # Kick off async turn handling with streaming
        self.busy = True
        asyncio.create_task(self._handle_turn(user_text))

        return True  # Don't insert a newline in the input field

    # --------------------------------------------------
    # Turn handling: where we call complete_turn
    # --------------------------------------------------
    async def _handle_turn(self, user_text: str) -> None:
        try:
            initial_turn = create_initial_turn(self.config, user_text)

            await complete_turn(
                initial_turn=initial_turn,
                config=self.config,
                client=self.client,
                tools=self.tools,
                ui=self.turn_ui,
            )

            # After streaming finishes, ensure we end the line
            current = self.chat_output.text or ""
            if not current.endswith("\n"):
                self.chat_output.text = current + "\n"
                self.chat_output.buffer.cursor_position = len(self.chat_output.text)
                self.app.invalidate()
        finally:
            self.busy = False

    # --------------------------------------------------
    # Run the app
    # --------------------------------------------------
    async def run(self) -> None:
        self.append_chat_line(
            "System", f"Welcome to {settings.ASSISTANT_NAME} TUI demo."
        )
        self.append_chat_line(
            "System",
            "Type a message and press Enter. "
            'Try "/reverse hello world" to call the demo tool.',
        )
        await self.app.run_async()


# ============================================================
# Entry point
# ============================================================


async def main():
    config = load_config_dummy()
    client = DummyClient()
    tools = await client.list_tools()

    ui = ChatUI(config=config, client=client, tools=tools)
    await ui.run()


if __name__ == "__main__":
    asyncio.run(main())
