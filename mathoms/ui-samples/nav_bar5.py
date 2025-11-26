#!/usr/bin/env python3
# Full-screen prompt_toolkit Application with:
# - Modern Nord-style color scheme
# - Clickable emoji top nav bar (mouse only)
# - Middle output area with scrollbar (PageUp/PageDown)
# - Bottom input that wraps long text as you type
#   (single logical line; Enter submits)

import asyncio
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType


def make_app() -> Application:
    # -------- Output panel (scrollable) --------
    output = TextArea(
        text=(
            "Welcome! Type in the box below.\n"
            "Long text in the input wraps as you type.\n"
            "Press Enter to submit. Ctrl-C to quit.\n"
            "Use PageUp/PageDown to scroll this output.\n\n"
            "Use your mouse to click the emoji menu items above 👆\n\n"
        ),
        scrollbar=True,
        focusable=True,
        wrap_lines=True,
        read_only=True,
        style="class:textarea",  # Nord background + text
    )

    def append_output(text: str) -> None:
        current = output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        output.text = current + text + "\n"
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
        append_output("[Models 🤖] model-a, model-b, model-c")

    def do_config():
        append_output("[Config ⚙️] example config value = 42")

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

        # Emoji + bold-ish Unicode letter labels
        add_item("🤖 𝗠𝗼𝗱𝗲𝗹𝘀", do_models)
        add_item("⚙️ 𝗖𝗼𝗻𝗳𝗶𝗴", do_config)
        add_item("❓ 𝗛𝗲𝗹𝗽", do_help)
        add_item("📄 𝗟𝗶𝗻𝗲𝘀", do_lines)

        # Trailing hint text: not clickable
        frags.append(("class:menu-hint", " Enter: Submit    Ctrl-C: Quit "))

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

    # Enter submits the wrapped, single logical line in the input
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

        append_output(f"You said: {text}")

    # -------- Style: modern Nord-like palette --------
    style = Style.from_dict(
        {
            "menu-bar": "bg:#F2F2F2 #37474F",
            "menu-item": "bg:#F2F2F2 #1E88E5 bold",
            "menu-sep": "bg:#F2F2F2 #CFD8DC",
            "menu-hint": "bg:#F2F2F2 #607D8B",
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
    return app


async def main():
    app = make_app()
    await app.run_async()


if __name__ == "__main__":
    asyncio.run(main())
