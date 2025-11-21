#!/usr/bin/env python3
"""
llm-ui.py

Full-screen prompt_toolkit UI that:

- Lets the user select a "scenario" before the app starts.
- Shows the scenario name in a top navbar.
- Has a scrollable output TextArea.
- Has a single-line input box at the bottom.
- On Enter, sends the text to an LLMEngine, which streams tokens
  back via PTKTurnUI into the output area.
"""

from typing import Any, List, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import is_done
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import (
    BufferControl,
    FormattedTextControl,
)
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.shortcuts import choice
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

# Your TurnUI implementation that the engine uses for streaming
from astrid.ptk_turn_ui import PTKTurnUI

# ---------------------------------------------------------------------------
# Main application factory
# ---------------------------------------------------------------------------


def make_app(
    scenario_key: str,
    scenario_label: str,
    engine: Any,  # typically main.LLMEngine
) -> Application:
    """
    Build and return the full-screen prompt_toolkit Application.

    `engine` must expose:
        async def handle_user_message(self, user_input: str, ui) -> None
    """

    # -------- Output panel (scrollable) --------
    output = TextArea(
        text=(
            f"Scenario selected: {scenario_label} ({scenario_key})\n\n"
            "Type something and press Enter.\n"
            "Commands: /lines, /config, /exit. Ctrl-C or Ctrl-D to quit.\n\n"
        ),
        scrollbar=True,
        focusable=True,
        wrap_lines=True,
        read_only=True,
        style="class:textarea",
    )

    # -------- Status bar (one line, under output) --------
    status_bar_control = FormattedTextControl(text=" Ready.")
    status_bar = Window(
        height=1,
        content=status_bar_control,
        style="class:status",
    )

    # -------- TurnUI adapter for streaming --------
    ui = PTKTurnUI(output=output, status_bar=status_bar_control)

    # -------- Top navbar --------
    def get_navbar_text():
        return [
            ("class:menu-item", " Astrid "),
            ("class:menu-sep", " | "),
            ("class:menu-item", "Scenario: "),
            ("class:scenario-label", scenario_label),
            ("class:menu-sep", " | "),
            ("class:menu-hint", "Ctrl-C / Ctrl-D or /exit to quit"),
        ]

    navbar = Window(
        height=1,
        content=FormattedTextControl(get_navbar_text),
        style="class:menu-bar",
    )

    # -------- Input: Buffer + BufferControl + Window --------
    input_buffer = Buffer(multiline=False)

    input_control = BufferControl(
        buffer=input_buffer,
        input_processors=[
            BeforeInput(lambda: "> ", style="class:prompt"),
        ],
        focusable=True,
    )

    input_window = Window(
        content=input_control,
        height=1,  # visible height in rows
        style="class:input",
    )

    # -------- Separators --------
    separator = Window(height=1, char="─", style="class:separator")

    # -------- Layout --------
    root_container = HSplit(
        [
            separator,
            navbar,
            separator,
            output,
            status_bar,
            separator,
            input_window,
        ]
    )

    layout = Layout(root_container, focused_element=input_window)

    # -------- Key bindings --------
    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("c-d")
    def _(event) -> None:
        """
        Ctrl-C / Ctrl-D: exit the app.
        """
        event.app.exit()

    @kb.add("enter")
    def _(event) -> None:
        """
        Enter: read user input, handle commands, or send to engine.
        """
        text = input_buffer.text.strip()
        input_buffer.text = ""  # clear input

        if not text:
            return

        # Built-in commands handled at UI level
        if text in ("/exit", "/quit"):
            event.app.exit()
            return

        if text == "/lines":
            ui.print("[demo] Line 1")
            ui.print("Line 2")
            ui.print("Line 3")
            return

        # Echo the user message into the output area
        ui.print(f"[user] {text}")

        async def run_turn():
            # Delegate to the engine (main.LLMEngine)
            await engine.handle_user_message(text, ui)

        # Schedule the coroutine without blocking the UI
        event.app.create_background_task(run_turn())

    # -------- Style --------
    style = Style.from_dict(
        {
            "menu-bar": "bg:#F2F2F2 #37474F",
            "menu-item": "bg:#F2F2F2 #1E88E5 bold",
            "menu-sep": "bg:#F2F2F2 #CFD8DC",
            "menu-hint": "bg:#F2F2F2 #607D8B",
            "scenario-label": "bg:#F2F2F2 #8E24AA bold",
            "prompt": "fg:#1E88E5 bold",
            "input": "bg:#FFFFFF #37474F",
            "textarea": "bg:#FAFAFA #424242",
            "separator": "bg:#F5F7FA #CBD2D9",
            "status": "bg:#E0E0E0 #455A64",
        }
    )

    # -------- App --------
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
        mouse_support=False,
    )

    # Convenience attributes if you want to inspect later
    app.scenario_key = scenario_key
    app.scenario_label = scenario_label

    return app


# ---------------------------------------------------------------------------
# Minimal standalone main (for debugging)
# ---------------------------------------------------------------------------


def main():
    """
    This UI module is meant to be driven from main.py, where the
    LLMEngine and MCP client are created.

    Running this file directly won't wire up a real engine.
    """
    print("This module is intended to be used from main.py (engine not wired here).")


if __name__ == "__main__":
    main()
