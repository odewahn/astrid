#!/usr/bin/env python3
"""
llm_ui.py

REPL-style prompt_toolkit UI that:

- Uses a PromptSession (no full-screen Application).
- Shows scenario name in a Rich-colored banner.
- Streams assistant tokens directly to stdout (raw; no Rich markup on tokens).
- Uses an indeterminate spinner/progress indicator on stderr whenever
  the engine calls ui.set_status(...) / ui.hide_status().
- Provides a bottom toolbar showing current status when the prompt
  is active.
- Uses a colored prompt string: [user]> in green.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Callable, Dict, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.patch_stdout import patch_stdout

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from astrid.settings import settings

# Single Rich console for stdout
console = Console()


# ---------------------------------------------------------------------------
# TurnUI implementation for REPL mode (with spinner + Rich for non-stream output)
# ---------------------------------------------------------------------------


class REPLTurnUI:
    """
    TurnUI implementation for the REPL:

    - Streams LLM tokens to stdout (raw; no Rich markup).
    - Interprets set_status / hide_status as "start / stop an indeterminate
      progress spinner" on stderr.
    - Uses a status callback so the bottom toolbar can reflect the current
      high-level state when the prompt is visible.
    - Uses Rich for non-streaming, line-oriented output via `print()`.
    """

    def __init__(
        self,
        set_status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._set_status_callback = set_status_callback or (lambda _text: None)

        self._spinner_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._spinner_label: str = ""
        self._last_render_len: int = 0

    # --- Internal spinner logic ----------------------------------------

    async def _spinner_worker(self) -> None:
        """
        Animate an indeterminate progress indicator on stderr.

        This runs until _stop_event is set.
        """
        frames = ["⣾", "⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽"]
        i = 0

        while self._stop_event and not self._stop_event.is_set():
            frame = frames[i % len(frames)]
            i += 1

            label = self._spinner_label or "Working"
            line = f"[{frame}] {label} (Ctrl-C to abort)"

            # Render on a single line, overwriting previous contents.
            render = "\r" + line
            pad = max(0, self._last_render_len - len(line))
            if pad:
                render += " " * pad

            sys.stderr.write(render)
            sys.stderr.flush()

            self._last_render_len = len(line)

            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

        # Clear the line when done.
        if self._last_render_len > 0:
            sys.stderr.write("\r" + " " * self._last_render_len + "\r")
            sys.stderr.flush()
            self._last_render_len = 0

    def _start_spinner(self, label: str) -> None:
        """
        Start (or update) the spinner for the given label.
        """
        self._spinner_label = label or "Working"

        # Notify any bottom-toolbar status
        self._set_status_callback(self._spinner_label)

        # If a spinner is already running, just update the label; worker
        # reads _spinner_label on each loop.
        if self._spinner_task and not self._spinner_task.done():
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: we're not in async context. In practice this
            # shouldn't happen because the engine runs under asyncio.
            return

        self._stop_event = asyncio.Event()
        self._spinner_task = loop.create_task(self._spinner_worker())

    def _stop_spinner(self) -> None:
        """
        Stop the spinner and clear the status.
        """
        # Reset logical status for bottom toolbar
        self._set_status_callback("")

        if self._stop_event is not None:
            self._stop_event.set()
        # Let the worker clear its line and exit; no need to cancel explicitly.

    # --- TurnUI interface used by LLMEngine / complete_turn -------------

    def set_status(self, text: str) -> None:
        """
        Called by the engine to indicate some long-running work is happening,
        e.g. "Generating response..." or "Running tools...".
        """
        label = text or "Working"
        self._start_spinner(label)

    def hide_status(self) -> None:
        """
        Called by the engine once the work is complete.
        """
        self._stop_spinner()

    def print_streaming_token(self, text: str) -> None:
        """
        Stream tokens directly to stdout as they arrive.

        We keep this raw (no Rich) so streaming is as simple and robust
        as possible.
        """
        sys.stdout.write(text)
        sys.stdout.flush()

    def print(self, text: str) -> None:
        """
        Print a full line or block of text, ensuring a single trailing newline.

        This uses Rich so any ANSI/style markup the engine includes can be
        rendered nicely.
        """
        if text is None:
            return

        # Avoid double newlines: strip a single trailing newline, let Rich add one.
        if text.endswith("\n"):
            text = text[:-1]

        console.print(text)


# ---------------------------------------------------------------------------
# REPL "app" wrapper
# ---------------------------------------------------------------------------


class ReplApp:
    """
    Small wrapper so main.py can still call `await app.run_async()`.

    This runs a PromptSession-based REPL that talks to the LLMEngine
    using REPLTurnUI.
    """

    def __init__(self, scenario_key: str, scenario_label: str, engine: Any) -> None:
        self.scenario_key = scenario_key
        self.scenario_label = scenario_label
        self.engine = engine

    async def run_async(self) -> None:
        """
        Run the REPL loop:

        - Prints a Rich-colored banner with scenario info.
        - Uses PromptSession for input (with history, editing, etc.).
        - Uses a bottom_toolbar as a simple status line when the prompt
          is active.
        - Streams LLM output via REPLTurnUI.
        - Prompt is colored: [user]> in green.
        """
        status: Dict[str, str] = {"text": ""}

        def set_status(text: str) -> None:
            # Called by REPLTurnUI whenever the spinner label changes,
            # or when hide_status() is called.
            status["text"] = text or ""

        def bottom_toolbar() -> str:
            # Shown only while waiting for user input (prompt visible).
            # When work is in progress, the indeterminate spinner is
            # rendered on stderr instead.
            human_status = status["text"] or "Idle"
            return (
                f" {settings.ASSISTANT_NAME} · {self.scenario_label} "
                f"| Status: {human_status} "
                "| /help /config /exit"
            )

        # Colorized prompt: entire "[user]> " in green
        prompt_message = HTML(f"<ansigreen>{settings.ASSISTANT_NAME}&gt; </ansigreen>")

        session = PromptSession(
            prompt_message,
            bottom_toolbar=bottom_toolbar,
        )

        ui = REPLTurnUI(set_status_callback=set_status)

        # Banner (Rich)
        title = Text(settings.ASSISTANT_NAME, style="bold cyan")
        subtitle = Text(f"{self.scenario_label} ({self.scenario_key})", style="magenta")
        banner_text = Text.assemble(title, Text(" – "), subtitle)

        console.print(
            Panel(
                banner_text,
                title="LLM Chat",
                border_style="cyan",
            )
        )
        console.print(
            "[bold]Type[/] [yellow]/help[/] [bold]for help,[/] "
            "[yellow]/config[/] [bold]for config,[/] "
            "[yellow]/exit[/] [bold]to quit.[/]\n"
        )

        # Main REPL loop
        while True:
            try:
                # Keep patch_stdout scoped to the prompt itself, so Rich
                # output (banner, help, engine prints) goes straight to
                # the terminal and colors render correctly.
                with patch_stdout():
                    user_input = await session.prompt_async()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold red]Exiting.[/]")
                break

            text = (user_input or "").strip()
            if not text:
                continue

            # Simple REPL-level commands
            if text in ("/exit", "/quit"):
                console.print("[bold red]Goodbye.[/]")
                break

            if text == "/help":
                console.print(
                    Panel(
                        Text.from_markup(
                            "[bold]Commands[/]\n"
                            "  [yellow]/help[/]    Show this help\n"
                            "  [yellow]/config[/]  Show current config (handled by engine)\n"
                            "  [yellow]/exit[/]    Quit\n\n"
                            "You can also just type any question or instruction."
                        ),
                        border_style="green",
                        title="Help",
                    )
                )
                continue

            # Everything else goes to the engine. It will handle /config,
            # tools, streaming, etc., and will drive the spinner via
            # ui.set_status(...) / ui.hide_status().
            await self.engine.handle_user_message(user_input, ui)

            # Make sure there's a newline after each assistant reply so
            # the next prompt doesn't jam right against the last token.
            sys.stdout.write("\n")
            sys.stdout.flush()


# ---------------------------------------------------------------------------
# Factory function expected by main.py
# ---------------------------------------------------------------------------


def make_app(
    scenario_key: str,
    scenario_label: str,
    engine: Any,
) -> ReplApp:
    """
    Build and return a REPL 'app' compatible with main.py.

    main.py does:

        app = make_app(...)
        await app.run_async()

    This version does *not* create a full-screen Application — it creates
    a ReplApp that manages a PromptSession-based REPL instead.
    """
    return ReplApp(
        scenario_key=scenario_key,
        scenario_label=scenario_label,
        engine=engine,
    )


# ---------------------------------------------------------------------------
# Standalone entry (not used in normal flow)
# ---------------------------------------------------------------------------


def main() -> None:
    """
    This UI module is meant to be driven from main.py, where the
    LLMEngine and MCP client are created.

    Running this file directly won't wire up a real engine.
    """
    console.print(
        "[bold yellow]This module is intended to be used from main.py "
        "(engine not wired here).[/]"
    )


if __name__ == "__main__":
    main()
