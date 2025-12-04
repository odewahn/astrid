# astrid/logging_setup.py
import logging
import os
from logging import StreamHandler

DEFAULT_LOG_FILE = "astrid.log"

NOISY_LOGGERS = [
    "LiteLLM",
    "litellm",
    "mcp",
    "mcp.server",
    "mcp.server.lowlevel.server",
    "mcp.client",
    "openai",
]


def configure_logging(
    log_file: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
) -> logging.Handler:
    """
    Configure a single file-only logging sink and prevent console pollution.
    Safe across LiteLLM/fastmcp versions (no imports here).
    """
    # Ensure LiteLLM (if/when imported) doesn't default to debug
    os.environ.setdefault("LITELLM_LOG", "ERROR")

    root = logging.getLogger()

    # 1) Remove ALL existing handlers (including basicConfig and any stream handlers)
    for h in list(root.handlers):
        root.removeHandler(h)

    # 2) Install a single FileHandler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(fmt)

    root.addHandler(file_handler)
    root.setLevel(level)

    # 3) Make root the only sink; prevent accidental console logging by children
    #    Also, for any logger names we know, force them to our file handler and stop propagation
    for name in NOISY_LOGGERS:
        l = logging.getLogger(name)
        # Wipe any existing handlers (incl. StreamHandler to stdout)
        for h in list(l.handlers):
            l.removeHandler(h)
        l.addHandler(file_handler)
        l.propagate = False
        l.setLevel(logging.DEBUG)

    # 4) Safety pass: remove any StreamHandler that might get added post-config
    _strip_console_handlers_globally()

    # 5) Optional: silence logging exceptions in production
    logging.raiseExceptions = False

    return file_handler


def _strip_console_handlers_globally():
    """Remove ANY StreamHandler attached anywhere (root + known libraries)."""
    # root
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, StreamHandler):
            root.removeHandler(h)

    # known libraries
    for name in NOISY_LOGGERS:
        l = logging.getLogger(name)
        for h in list(l.handlers):
            if isinstance(h, StreamHandler):
                l.removeHandler(h)
