#!/usr/bin/env python3
# Full-screen prompt_toolkit Application with:
# - Scenario selection before app starts
# - Scenario name shown in the header bar
# - Modern Nord-style color scheme
# - Clickable emoji top nav bar (mouse only)
# - Middle output area with scrollbar (PageUp/PageDown)
# - Bottom input that wraps long text as you type
#   (single logical line; Enter submits)

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


# ------- Scenario selection config --------
SCENARIOS = [
    ("scenario1", "Do the first scenario"),
    ("scenario2", "Second Scenario"),
    ("scenario3", "Third Scenario"),
]


def select_scenario() -> str:
    """
    Show a blocking choice() prompt before the TUI starts.
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


def make_app(scenario_key: str, scenario_label: str) -> Application:
    # -------- Output panel (scrollable) --------
    output = TextArea(
        text=(
            f"Scenario selected: {scenario_label} ({scenario_key})\n\n"
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
        style="class:textarea",
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
        height=2,
        wrap_lines=True,
        style="class:input",
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
        """
        frags = []

        def add_item(label, callback):
            def handler(mouse_event):
                if mouse_event.event_type == MouseEventType.MOUSE_UP:
                    callback()

            frags.append(("class:menu-item", f" {label} ", handler))
            frags.append(("class:menu-sep", "  "))

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

    # -------- Key bindings --------
    kb = KeyBindings()

    @kb.add("c-c")
    def _(event) -> None:
        event.app.exit()

    @kb.add("enter")
    def _(event) -> None:
        text = input_buffer.text.strip()
        input_buffer.text = ""

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

        append_output(f"[{scenario_key}] You said: {text}")

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
        }
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=style,
        mouse_support=True,
    )

    app.scenario_key = scenario_key
    app.scenario_label = scenario_label

    return app


def main():
    # First, blockingly ask for scenario (sync, safe to use choice()).
    scenario_key = select_scenario()
    scenario_label = dict(SCENARIOS)[scenario_key]

    app = make_app(scenario_key=scenario_key, scenario_label=scenario_label)
    # Run app synchronously; this uses asyncio.run() internally.
    app.run()


if __name__ == "__main__":
    main()
