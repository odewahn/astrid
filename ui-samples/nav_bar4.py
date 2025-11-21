#!/usr/bin/env python3
# Full-screen prompt_toolkit Application with:
# - Prominent, clickable emoji top nav bar
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
        height=3,  # visible height in rows
        wrap_lines=True,  # wraps soft across lines
    )

    # -------- Menu item actions (used by mouse only) --------
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

    # -------- Pinned nav bar with “big” clickable emoji menu items --------
    def nav_fragments():
        """
        Return a list of (style, text[, mouse_handler]) tuples.

        Clickable items = 3-tuples with a mouse handler.
        Non-clickable text = 2-tuples.
        """
        frags = []

        # Top padding line (adds visual height)
        frags.append(("class:menu-bar", " "))  # small spacer at top
        frags.append(("class:menu-bar", "\n"))

        def add_item(label, callback):
            # label example: "🤖 𝗠𝗼𝗱𝗲𝗹𝘀"
            def handler(mouse_event):
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    callback()

            frags.append(("class:menu-bar.item", f"  {label}  ", handler))
            frags.append(("class:menu-bar.separator", "  "))

        # Use emojis + bold-ish Unicode letters to feel “larger”
        add_item("🤖 𝗠𝗼𝗱𝗲𝗹𝘀", do_models)
        add_item("⚙️ 𝗖𝗼𝗻𝗳𝗶𝗴", do_config)
        add_item("❓ 𝗛𝗲𝗹𝗽", do_help)
        add_item("📄 𝗟𝗶𝗻𝗲𝘀", do_lines)

        # Trailing info: non-clickable
        frags.append(
            (
                "class:menu-bar.hint",
                " Enter: Submit | Ctrl-C: Quit | PgUp/PgDn: Scroll output",
            )
        )

        return frags

    navbar = Window(
        height=2,  # <--- makes the bar visually thicker
        content=FormattedTextControl(nav_fragments, show_cursor=False),
        style="class:menu-bar",
    )

    # -------- Layout --------
    root = HSplit([navbar, output, input_window])
    layout = Layout(root, focused_element=input_window)

    # -------- Key bindings (only for core behavior: enter, scroll, quit) --------
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event) -> None:
        event.app.exit()

    # PageUp/PageDown scroll the output a few lines
    @kb.add("pageup")
    def _(event) -> None:
        output.buffer.cursor_up(count=5)

    @kb.add("pagedown")
    def _(event) -> None:
        output.buffer.cursor_down(count=5)

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

    # -------- Style: chunky, high-contrast menu bar --------
    style = Style.from_dict(
        {
            # Whole bar: dark background, bright text, bold
            "menu-bar": "bg:#111111 #ffffff bold",
            # Clickable items: same background, a bit of extra emphasis
            "menu-bar.item": "bg:#111111 #ffffff bold",
            # Separator between items: slightly dimmer
            "menu-bar.separator": "bg:#111111 #888888 bold",
            # Trailing hint text
            "menu-bar.hint": "bg:#111111 #bbbbbb",
            # Prompt in input
            "prompt": "fg:#00ffff bold",
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
