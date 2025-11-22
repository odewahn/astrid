### Project Overview

This is a terminal-based chat client for an LLM, built around:

- **`prompt_toolkit`** for a full-screen TUI
- An **LLM + tools “engine”** in `main.py`
- A **prompt_toolkit-based TurnUI adapter** in `astrid/ptk_turn_ui.py`
- A **UI factory** living in `astrid/llm_ui.py`

The goal is: a streaming, tool-using LLM chat experience in a single terminal window with a clean separation between **engine** and **UI**.

---

### How the UI Looks and Behaves

The main chat UI is a full-screen app with:

- **Output area**

  - A scrollable `TextArea` showing the full conversation (system, user, assistant).
  - Read-only, line-wrapped, with an internal scrollbar.
  - LLM tokens stream directly into this area as they arrive.

- **Status bar**

  - A one-line bar under the output.
  - Shows transient messages like “Generating response…”, “Copied all output to clipboard.”, etc.

- **Input line**

  - A single-line input at the bottom, implemented via a `Buffer` + `BufferControl`.
  - Has a fixed prompt prefix (e.g. `"> "`).
  - Enter sends the text to the LLM engine.

- **Key bindings / commands**

  - `Enter` — send the current line to the LLM.
  - `/exit` or `/quit` — exit the application.
  - `/config` — print current config info (handled by the engine).
  - `/lines` — demo command that prints a few lines to the output.
  - `Ctrl-C` / `Ctrl-D` — quit the app.
  - (Optionally) `Ctrl-Y` — copy all output to the system clipboard using prompt_toolkit’s clipboard integration.

The UI is designed so the user mostly lives in the input line, sending messages and watching streamed responses.

---

### Core Architecture

There are three main layers:

#### 1. Engine (`main.py`)

- Responsible for:

  - Loading config (e.g. system prompts, model settings, tool config).
  - Creating and managing an async `Client` for the LLM + MCP tools.
  - Converting MCP tools to OpenAI tool format.
  - Orchestrating a single turn of conversation with streaming and tool calls.

Key pieces:

- **`LLMEngine`**

  - Holds `config`, `client`, and `tools`.
  - `initialize()` calls `client.list_tools()` and prepares tool definitions for OpenAI.
  - `handle_user_message(user_input, ui)`:

    - Handles simple commands like `/config`.
    - Builds an initial `Turn` with `create_initial_turn(config, user_input)`.
    - Calls `complete_turn(...)`, passing the `ui` so streaming can be displayed.

- **`complete_turn(...)`** (still a free function)

  - Takes the current `Turn`, config, tools, `Client`, and a `ui`.
  - Streams the assistant response token-by-token.
  - Emits intermediate tool calls and tool results as needed.
  - Uses the `ui` abstraction to:

    - `set_status(...)` / `hide_status()`
    - `print_streaming_token(text)` for each streamed chunk
    - `print(text)` for full lines / messages

The **engine does not know about prompt_toolkit** — it only depends on the `ui` interface.

---

#### 2. TurnUI Adapter (`astrid/ptk_turn_ui.py`)

This is a small adapter class that makes the prompt_toolkit widgets look like the `TurnUI` the engine expects.

Rough responsibilities:

- Initialized with:

  - `output`: the `TextArea` where conversation text is shown.
  - `status_bar`: the `FormattedTextControl` driving the status bar.

- Methods:

  - `set_status(text)` — updates the status bar text and invalidates the application.
  - `hide_status()` — clears the status bar.
  - `print_streaming_token(text)` — appends raw tokens to `output.text` and keeps the cursor at the end.
  - `print(text)` — appends complete lines to `output.text`, adding a newline if needed.

Critically, it **does not add extra spaces** between tokens; it just concatenates whatever the model streams, so punctuation and spacing are preserved correctly.

---

#### 3. UI Module (`astrid/llm_ui.py`)

This module builds and returns a `prompt_toolkit.application.Application` that uses the engine + TurnUI adapter.

Key function:

- **`make_app(scenario_key, scenario_label, engine)`**

  - Creates:

    - The `output` `TextArea`.
    - The `status_bar` `Window`.
    - The top navbar (`Window` with `FormattedTextControl` describing the app and scenario).
    - The input `Buffer`, `BufferControl`, and input `Window`.
    - A vertical `HSplit` combining navbar, output, status, and input into a layout.

  - Constructs a `PTKTurnUI(output, status_bar_control)` and passes it into the engine’s `handle_user_message` calls.
  - Sets up key bindings:

    - `Enter` reads `input_buffer.text`, clears it, handles `/exit`/`/quit`/`/lines`, echoes `[user] ...` to the output, then schedules `engine.handle_user_message(text, ui)` via `event.app.create_background_task(...)`.
    - `Ctrl-C` / `Ctrl-D` exit the app.
    - Optionally `Ctrl-Y` copies output to clipboard using a `PyperclipClipboard`.

The `Application` is created with:

- `full_screen=True`
- `mouse_support=True` (so prompt_toolkit can handle mouse events in terminals that support it)
- A custom `Style` for navbar, input, textarea, separator, status.

Scrolling is primarily via the `TextArea`’s internal scrollbar (keyboard scrolling is reliable; mouse-wheel behavior depends on the terminal).

---

### Entry Point / Control Flow

At program startup (`main.py`):

1. Parse CLI args, load config.
2. Create `Client(config)`.
3. Create `LLMEngine(config, client)` and `await engine.initialize()`.
4. Build the UI app with `make_app(..., engine=engine)`.
5. Run it with `await app.run_async()` inside a single `asyncio.run(runner())`.

From there:

- Every user input line → `engine.handle_user_message(text, ui)` → `complete_turn(...)` → streamed tokens route back through `PTKTurnUI` into the TextArea.

---

### Useful Constraints / Notes

- The engine is async and streaming; **UI must not block**. All long-running calls are scheduled via `event.app.create_background_task(...)`.
- `complete_turn` and `LLMEngine` don’t know about prompt_toolkit; they only depend on a small `ui` interface.
- Copying text is best done via a keybinding (e.g., `Ctrl-Y` to copy the entire transcript), rather than mouse drag, because mouse reporting conflicts with native terminal selection.
- Scrolling behavior is terminal-dependent. The TextArea supports internal scroll via keyboard; mouse wheel behavior varies between VS Code’s terminal and macOS Terminal.
