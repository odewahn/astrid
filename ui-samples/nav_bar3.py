#!/usr/bin/env python3
import asyncio
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style
from prompt_toolkit.mouse_events import MouseEventType  # <-- NEW


class NavState:
    def __init__(self) -> None:
        self.default_message = (
            "Ctrl-X M: Models | Ctrl-X C: Config | Ctrl-X H: Help | "
            "Ctrl-X L: Lines | Enter: Submit | Ctrl-C: Quit | PgUp/PgDn: Scroll output"
        )
        self.message = self.default_message

    def set(self, text: str) -> None:
        self.message = text

    def reset(self) -> None:
        self.message = self.default_message


def make_app() -> Application:
    nav = NavState()

    # -------- Output panel (scrollable) --------
    output = TextArea(
        text=(
            "Welcome! Type in the box below.\n"
            "Long text in the input wraps as you type.\n"
            "Press Enter to submit. Ctrl-C to quit.\n"
            "Use PageUp/PageDown to scroll this output.\n\n"
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
        height=3,
        wrap_lines=True,
    )

    # -------- Menu item actions (shared by keys + mouse) --------
    def do_models():
        nav.set("Models: model-a, model-b, model-c")
        append_output("[Models] model-a, model-b, model-c")
        nav.reset()

    def do_config():
        nav.set("Config: demo config")
        append_output("[Config] example config value = 42")
        nav.reset()

    def do_help():
        nav.set("Help: /lines, /exit; Enter submit, Ctrl-C quit")
        append_output("[Help] Commands: /lines, /exit. Enter=submit, Ctrl-C=quit")
        nav.reset()

    def do_lines():
        nav.set("Printing lines...")
        append_output("Line 1")
        append_output("Line 2")
        append_output("Line 3")
        nav.reset()

    # -------- Pinned nav bar with mouse handlers --------
    from prompt_toolkit.mouse_events import MouseEventType

    def nav_fragments():
        """
        Return a list of (style, text[, mouse_handler]) tuples.

        Clickable items get a mouse handler (3-tuple).
        Non-clickable bits are plain 2-tuples.
        """
        frags = []

        def add_item(label, hint, callback):
            def handler(mouse_event):
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    callback()

            # clickable part
            text = f"{hint} {label}"
            frags.append(("class:menu-bar", text, handler))

            # separator: non-clickable → 2-tuple
            frags.append(("class:menu-bar", " | "))

        add_item("Models", "Ctrl-X M:", do_models)
        add_item("Config", "Ctrl-X C:", do_config)
        add_item("Help", "Ctrl-X H:", do_help)
        add_item("Lines", "Ctrl-X L:", do_lines)

        # trailing text: also non-clickable → 2-tuple
        frags.append(
            (
                "class:menu-bar",
                " Enter: Submit | Ctrl-C: Quit | PgUp/PgDn: Scroll output",
            )
        )

        return frags

    navbar = Window(
        height=1,
        content=FormattedTextControl(nav_fragments),
        style="class:menu-bar",
    )

    # -------- Layout --------
    root = HSplit([navbar, output, input_window])
    layout = Layout(root, focused_element=input_window)

    # -------- Key bindings --------
    kb = KeyBindings()

    @kb.add("c-x", "m")
    def _(event) -> None:
        do_models()

    @kb.add("c-x", "c")
    def _(event) -> None:
        do_config()

    @kb.add("c-x", "h")
    def _(event) -> None:
        do_help()

    @kb.add("c-x", "l")
    def _(event) -> None:
        do_lines()

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

    # -------- Style --------
    style = Style.from_dict(
        {
            "menu-bar": "bg:#000000 #ffffff",
            "prompt": "fg:#00ffff bold",
        }
    )

    # -------- App --------
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
        mouse_support=True,  # <-- required for clicks to be sent
    )
    return app


async def main():
    app = make_app()
    await app.run_async()


if __name__ == "__main__":
    asyncio.run(main())
