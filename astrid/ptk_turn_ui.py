from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea


class PTKTurnUI:
    """
    Drop-in replacement for TurnUI in main.py, but backed by prompt_toolkit widgets.
    Needs to provide: set_status, hide_status, print_streaming_token, print.
    """

    def __init__(self, output: TextArea, status_bar: FormattedTextControl):
        self.output = output
        self.status_bar = status_bar

    # --- Helpers ---
    def _invalidate(self):
        try:
            get_app().invalidate()
        except Exception:
            pass

    # --- TurnUI API ---

    def set_status(self, text: str) -> None:
        self.status_bar.text = f" {text}"
        self._invalidate()

    def hide_status(self) -> None:
        self.status_bar.text = ""
        self._invalidate()

    def print_streaming_token(self, text: str) -> None:
        current = self.output.text or ""
        self.output.text = current + text
        self.output.buffer.cursor_position = len(self.output.text)
        self._invalidate()

    def print(self, text: str) -> None:
        current = self.output.text or ""
        if current and not current.endswith("\n"):
            current += "\n"
        current += text + "\n"
        self.output.text = current
        self.output.buffer.cursor_position = len(self.output.text)
        self._invalidate()
