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


from rich.status import Status
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
        self._set_status_callback = set_status_callback
        self._rich_status = None
        self._characters_printed = (
            0  # Track chars printed on current line for streaming
        )

    # --- TurnUI interface used by LLMEngine / complete_turn -------------

    def set_status(self, text: str) -> None:
        # Update optional prompt-toolkit toolbar
        if self._set_status_callback:
            self._set_status_callback(text)

        # Create or update a Rich status spinner
        if self._rich_status is None:
            self._rich_status = console.status(text, spinner="dots")
            self._rich_status.__enter__()  # show spinner
        else:
            self._rich_status.update(text)

    def hide_status(self) -> None:
        # Clear bottom toolbar if used
        if self._set_status_callback:
            self._set_status_callback("")

        # Stop and remove the spinner
        if self._rich_status is not None:
            self._rich_status.__exit__(None, None, None)
            self._rich_status = None

    def print_streaming_token(self, text: str) -> None:
        """
        Stream tokens directly to stdout as they arrive.

        We keep this raw (no Rich) so streaming is as simple and robust
        as possible.
        """
        max_width = (console.size.width - 1) if console else 80

        # If printing the token would put us over the max_width, add a newline first
        # and then reset the character count.
        if self._characters_printed + len(text) > max_width:
            sys.stdout.write("\n")
            sys.stdout.write(text)
            sys.stdout.flush()
            self._characters_printed = len(text)
            return

        # If the token contains newlines, we need to reset the character count
        # after the last newline.
        if "\n" in text:
            self._characters_printed = 0
        else:
            self._characters_printed += len(text)

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
        self._characters_printed = 0


# ---------------------------------------------------------------------------
# REPL "app" wrapper
# ---------------------------------------------------------------------------
def print_credentials(console) -> None:
    console.print("\n")
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]Console Login Credentials[/]\n\n"
                f"Copy/paste the following credentials to log into the lab's companion console.\n"
                f"Be sure to use private browsing window to prevent conflicts with other sessions.\n\n"
                f"  [blue]URL:[/] {settings.console_url}\n"
                f"  [yellow]Username:[/] {settings.console_username}\n"
                f"  [yellow]Password:[/] {settings.console_password}\n"
                f"\nYou can repeat this command at any time by typing [yellow]/creds[/]."
            ),
            border_style="green",
            title="Credentials",
        )
    )
    console.print("\n")


def print_help(console) -> None:
    console.print("\n")
    console.print(
        Panel(
            Text.from_markup(
                f"[bold]Help - Available Commands[/]\n\n"
                f"  [yellow]/help[/]      Show this help message.\n"
                f"  [yellow]/config[/]    Display the current configuration.\n"
                f"  [yellow]/creds[/]     Show console login credentials.\n"
                f"  [yellow]/exit[/]      Exit the application.\n"
                f"\nType your message and press Enter to interact with the assistant."
            ),
            border_style="blue",
            title="Help",
        )
    )
    console.print("\n")
