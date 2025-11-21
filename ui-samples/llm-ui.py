#!/usr/bin/env python3
"""
Full-screen prompt_toolkit app with:

- Scenario selection before the app starts (using `choice`).
- Scenario name displayed in the header bar.
- Output area with scrollbar.
- Single-line input at the bottom.
- When user presses Enter, the response is streamed word-by-word
  on a single line, typewriter-style (like an LLM).
"""

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType

from prompt_toolkit.shortcuts import choice
from prompt_toolkit.filters import is_done

import asyncio


# ------- Scenario selection config --------
SCENARIOS = [
    ("scenario1", "Do the first scenario"),
    ("scenario2", "Second Scenario"),
    ("scenario3", "Third Scenario"),
]


def select_scenario() -> str:
    """
    Blocking scenario picker shown before the TUI starts.
    Returns the scenario key, e.g. 'scenario1'.
    """
    scenario_style = Style.from_dict(
        {
            "frame.border": "#884444",
            "selected-option": "bold",
        }
    )

    result = choice(
        message="Please select a scenario:",
        options=SCENARIOS,
        style=scenario_style,
        show_frame=~is_done,
    )
    return result


# ------- Example async generator representing the streaming process --------
async def stream_response(prompt: str):
    """
    Example streaming generator.

    For demo purposes, it just streams the *words* of the user's prompt,
    one at a time. Replace this with your real LLM / backend streaming.
    """
    # Simulate some processing delay and token streaming.
    for word in prompt.split():
        await asyncio.sleep(0.25)  # simulate network/compute delay
        yield word


def make_app(scenario_key: str, scenario_label: str) -> Application:
    # -------- Output panel (scrollable) --------
    output = TextArea(
        text=(
            f"Scenario selected: {scenario_label} ({scenario_key})\n\n"
            "Type something and press Enter.\n"
            "The response will stream word-by-word on a single line.\n"
            "Commands: /lines, /exit. Ctrl-C to quit.\n\n"
        ),
        scrollbar=True,
        focusable=True,
        wrap_lines=True,
        read_only=True,
        style="class:textarea",
    )

    def append_output(text: str) -> None:
        """
        Normal line-append helper (for non-streaming messages).
        """
        current = output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        output.text = current + text + "\n"
        output.buffer.cursor_position = len(output.text)

    # ---- Helpers for streaming on a single line ----

    def start_stream_line(prefix: str) -> None:
        """
        Start a new line that we'll keep appending tokens to,
        without immediately ending with a newline.
        """
        current = output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        # Start the line with a prefix, e.g. "[assistant] "
        output.text = current + prefix
        output.buffer.cursor_position = len(output.text)

    def append_stream_token(token: str) -> None:
        """
        Append a single token (word/char) to the current stream line.
        """
        text = output.text or ""

        # Insert a space if we are in the middle of a line and not after a space
        if text and not text.endswith((" ", "\n")):
            text += " "

        text += token
        output.text = text
        output.buffer.cursor_position = len(output.text)

    def end_stream_line() -> None:
        """
        Finish the current stream line with a newline.
        """
        text = output.text or ""
        if not text.endswith("\n"):
            text += "\n"
        output.text = text
        output.buffer.cursor_position = len(output.text)

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
        height=2,  # visible height in rows
        wrap_lines=True,  # wraps soft across lines
        style="class:input",  # Nord-style input background
    )

    # -------- Menu item actions (mouse only) --------
    def do_models():
        append_output(
            f"[Models 🤖] (scenario={scenario_key}) model-a, model-b, model-c"
        )

    def do_config():
        append_output(f"[Config ⚙️] (scenario={scenario_key}) example config value = 42")

    def do_help():
        append_output("[Help ❓] Commands: /lines, /exit. Enter=submit, Ctrl-C=quit")

    def do_lines():
        append_output("[Lines 📄]")
        append_output("Line 1")
        append_output("Line 2")
        append_output("Line 3")

    # -------- Pinned nav bar with modern, bold items --------
    def nav_fragments():
        """
        Return a list of (style, text[, mouse_handler]) tuples.

        Clickable items = 3-tuples with a mouse handler.
        Non-clickable text = 2-tuples.
        """
        frags = []

        def add_item(label, callback):
            def handler(mouse_event):
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    callback()

            # Clickable bold item
            frags.append(("class:menu-item", f" {label} ", handler))
            # Subtle spacing between items (not clickable)
            frags.append(("class:menu-sep", "  "))

        # Emoji + labels
        add_item("🤖 𝗠𝗼𝗱𝗲𝗹𝘀", do_models)
        add_item("⚙️ 𝗖𝗼𝗻𝗳𝗶𝗴", do_config)
        add_item("❓ 𝗛𝗲𝗹𝗽", do_help)
        add_item("📄 𝗟𝗶𝗻𝗲𝘀", do_lines)

        # Scenario label in the header
        frags.append(("class:menu-sep", "  |  "))
        frags.append(("class:scenario-label", f"Scenario: {scenario_label} "))

        # Trailing hint text: not clickable
        frags.append(("class:menu-hint", "   Enter: Submit    Ctrl-C: Quit "))

        return frags

    navbar = Window(
        height=1,
        content=FormattedTextControl(nav_fragments, show_cursor=False),
        style="class:menu-bar",
    )

    # -------- Layout --------

    separator = Window(
        height=1,
        char="─",
        style="class:separator",
    )

    root = HSplit([separator, navbar, separator, output, separator, input_window])
    layout = Layout(root, focused_element=input_window)

    # -------- Key bindings (core only: enter, scroll, quit) --------
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event) -> None:
        event.app.exit()

    @kb.add("enter")
    def _(event) -> None:
        text = input_buffer.text.strip()
        input_buffer.text = ""  # clear input

        if not text:
            return

        if text == "/exit":
            event.app.exit()
            return

        if text == "/lines":
            append_output("[red]Line 1")
            append_output("Line 2")
            append_output("Line 3")
            return

        # Start a fresh "assistant" stream line
        start_stream_line("[assistant]")

        async def run_stream():
            # Stream tokens from the async generator
            async for token in stream_response(text):
                append_stream_token(token)
                # Ask prompt_toolkit to redraw with the updated text
                event.app.invalidate()
            # When the stream ends, finish the line
            end_stream_line()
            event.app.invalidate()

        # Run streaming in the background so the UI stays responsive
        event.app.create_background_task(run_stream())

    # -------- Style: modern Nord-like palette --------
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
        }
    )

    # -------- App --------
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
        mouse_support=True,  # needed for clickable menu
    )
    app.scenario_key = scenario_key
    app.scenario_label = scenario_label

    return app


def main():
    # First, blockingly ask for scenario (this uses its own internal asyncio loop).
    scenario_key = select_scenario()
    scenario_label = dict(SCENARIOS)[scenario_key]

    # Then build and run the main TUI app (also manages its own asyncio loop).
    app = make_app(scenario_key=scenario_key, scenario_label=scenario_label)
    app.run()


if __name__ == "__main__":
    main()
