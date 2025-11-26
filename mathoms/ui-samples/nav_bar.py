#!/usr/bin/env python3
# Full-screen prompt_toolkit Application with:
# - Pinned top nav bar (white on black)
# - Middle output area
# - Bottom input that wraps long text as you type
#   (single logical line; Enter submits)

import asyncio
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style


class NavState:
    def __init__(self) -> None:
        self.default_message = (
            "Ctrl-X M: Models | Ctrl-X C: Config | Ctrl-X H: Help | "
            "Ctrl-X L: Lines | Enter: Submit | Ctrl-C: Quit"
        )
        self.message = self.default_message

    def set(self, text: str) -> None:
        self.message = text

    def reset(self) -> None:
        self.message = self.default_message


def make_app() -> Application:
    nav = NavState()

    # -------- Output panel (simple TextArea) --------
    output = TextArea(
        text=(
            "Welcome! Type in the box below.\n"
            "Long text in the input wraps as you type.\n"
            "Press Enter to submit. Ctrl-C to quit.\n\n"
        ),
        scrollbar=True,
        focusable=False,
        wrap_lines=True,
        read_only=True,
    )

    def append_output(text: str) -> None:
        current = output.text
        if current and not current.endswith("\n"):
            current += "\n"
        output.text = current + text + "\n"
        output.buffer.cursor_position = len(output.text)

    # -------- Input: Buffer + BufferControl + Window --------
    # Single logical line (multiline=False), but we wrap visually in the Window.
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
        height=3,  # <= visible height in rows
        wrap_lines=True,  # <= crucial: wraps soft across lines
    )

    # -------- Pinned nav bar --------
    navbar = Window(
        height=1,
        content=FormattedTextControl(
            lambda: HTML("<menu-bar>" + nav.message + "</menu-bar>")
        ),
        style="class:menu-bar",
    )

    # -------- Layout --------
    root = HSplit([navbar, output, input_window])
    layout = Layout(root, focused_element=input_window)

    # -------- Key bindings --------
    kb = KeyBindings()

    @kb.add("c-x", "m")
    def _(event) -> None:
        nav.set("Models: model-a, model-b, model-c")
        append_output("[Models] model-a, model-b, model-c")
        nav.reset()

    @kb.add("c-x", "c")
    def _(event) -> None:
        nav.set("Config: demo config")
        append_output("[Config] example config value = 42")
        nav.reset()

    @kb.add("c-x", "h")
    def _(event) -> None:
        nav.set("Help: /lines, /exit; Enter submit, Ctrl-C quit")
        append_output("[Help] Commands: /lines, /exit. Enter=submit, Ctrl-C=quit")
        nav.reset()

    @kb.add("c-x", "l")
    def _(event) -> None:
        nav.set("Printing lines...")
        append_output("Line 1")
        append_output("Line 2")
        append_output("Line 3")
        nav.reset()

    @kb.add("c-c")
    def _(event) -> None:
        event.app.exit()

    # Enter submits the wrapped, single logical line
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
            append_output("Line 1")
            append_output("Line 2")
            append_output("Line 3")
            return

        append_output(f"You said: {text}")

    # -------- Style: white text on black bar, cyan prompt --------
    style = Style.from_dict(
        {
            "menu-bar": "bg:#000000 #ffffff",  # black background, white text
            "prompt": "fg:#00ffff bold",  # cyan prompt
        }
    )

    # -------- App --------
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
    )
    return app


async def main():
    app = make_app()
    await app.run_async()


if __name__ == "__main__":
    asyncio.run(main())
