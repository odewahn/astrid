# astrid/repl_turn_ui.py

import sys
import asyncio
from typing import Callable, Optional


class REPLTurnUI:
    """
    TurnUI implementation for the REPL:

    - Streams LLM tokens to stdout.
    - Uses set_status/hide_status to drive an indeterminate progress spinner
      on stderr (one-line bar that updates in place).
    - Optionally notifies a status callback (for PromptSession bottom_toolbar).
    """

    def __init__(
        self,
        set_status_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._set_status_callback = set_status_callback or (lambda _text: None)

        self._spinner_task: Optional[asyncio.Task] = None
        self._spinner_label: str = ""
        self._stop_event: Optional[asyncio.Event] = None

    # --- internal spinner logic ----------------------------------------

    async def _spinner_worker(self) -> None:
        # Simple "indeterminate progress bar" with spinner-like frames.
        frames = ["⣾", "⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽"]
        i = 0

        label = self._spinner_label or "Working"

        while self._stop_event and not self._stop_event.is_set():
            frame = frames[i % len(frames)]
            i += 1

            line = f"\r[{frame}] {label} (Ctrl-C to abort)"
            sys.stderr.write(line)
            sys.stderr.flush()

            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

        # Clear the line when done
        clear_width = len(self._spinner_label) + len("[( )]  (Ctrl-C to abort)") + 4
        sys.stderr.write("\r" + " " * clear_width + "\r")
        sys.stderr.flush()

    def _start_spinner(self, label: str) -> None:
        """
        Start (or update) the spinner for the given label.
        """
        self._spinner_label = label or "Working"

        # notify bottom_toolbar (if any)
        self._set_status_callback(self._spinner_label)

        # If we already have a spinner running, just update the label.
        if self._spinner_task and not self._spinner_task.done():
            return

        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        self._spinner_task = loop.create_task(self._spinner_worker())

    def _stop_spinner(self) -> None:
        """
        Stop the spinner and clear the status.
        """
        # notify bottom_toolbar (if any)
        self._set_status_callback("")

        if self._stop_event is not None:
            self._stop_event.set()

        if self._spinner_task is not None and not self._spinner_task.done():
            # Let the worker clear the line and exit gracefully
            # (no need to cancel; setting the event is enough)
            pass

    # --- TurnUI interface ----------------------------------------------

    def set_status(self, text: str) -> None:
        """
        Engine calls this to indicate we're doing work.

        We interpret it as: "show/keep an indeterminate progress bar with this label".
        """
        label = text or "Working"
        self._start_spinner(label)

    def hide_status(self) -> None:
        """
        Engine calls this when the work is done.

        We interpret it as: "stop and erase the progress bar".
        """
        self._stop_spinner()

    def print_streaming_token(self, text: str) -> None:
        """
        Stream tokens directly to stdout, as usual.
        """
        sys.stdout.write(text)
        sys.stdout.flush()

    def print(self, text: str) -> None:
        """
        Print a full line of text, ensuring a trailing newline.
        """
        if text is None:
            return

        if not text.endswith("\n"):
            text = text + "\n"

        sys.stdout.write(text)
        sys.stdout.flush()
