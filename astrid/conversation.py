from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any

from openai.types.chat import ChatCompletionToolParam
from litellm.utils import Message, Usage
import json


class Step(BaseModel):
    message: Message
    usage: Optional[Usage] = None


class Turn(BaseModel):
    steps: List[Step] = Field(default_factory=list)
    summary: Optional[str] = None
    loop_count: int = 0

    # Internal helper to add a step
    def _add_step(
        self,
        *,
        role: str,
        usage: Optional[Usage] = None,
        message: Optional[Union[Message, dict]] = None,
        **msg_kwargs: Any,
    ) -> None:
        """
        Internal helper to normalize Message/dict and append a Step.
        Either pass `message` directly or kwargs to build one.
        """
        if message is None:
            # Build a new Message from kwargs
            message = Message(role=role, **msg_kwargs)
        else:
            # Normalize dict -> Message
            if not isinstance(message, Message):
                message = Message(**message)

        self.steps.append(Step(message=message, usage=usage))

    # Thin, role-specific helpers:

    def add_system(self, content: str, **extra: Any) -> None:
        self._add_step(role="system", content=content, **extra)

    def add_user(self, content: str, **extra: Any) -> None:
        self._add_step(role="user", content=content, **extra)

    def add_assistant(
        self, content: str, usage: Optional[Usage] = None, **extra: Any
    ) -> None:
        self._add_step(role="assistant", content=content, usage=usage, **extra)

    def add_tool(
        self,
        name: str,
        content: str,
        tool_call_id: Optional[str] = None,
        **extra: Any,
    ) -> None:
        self._add_step(
            role="tool",
            name=name,
            content=content,
            tool_call_id=tool_call_id,
            **extra,
        )

    def add_raw(
        self, message: Union[Message, dict], usage: Optional[Usage] = None
    ) -> None:
        """
        For already-structured assistant messages (e.g. from stream_chunk_builder),
        but also tolerant of raw dicts.
        """
        self._add_step(role="assistant", message=message, usage=usage)

    # get_exchange returns the first user message and the last assistant message
    # i.e., it's what the user asked and what the model finally responded without
    # any intermediate tool calls or system messages.
    def get_exchange(self) -> Optional[tuple[Step, Step]]:
        user_step: Optional[Step] = None
        assistant_step: Optional[Step] = None

        for step in self.steps:
            if step.message.role == "user":
                if user_step is None:
                    user_step = step
            elif step.message.role == "assistant":
                assistant_step = step

        if user_step is not None and assistant_step is not None:
            return user_step, assistant_step
        return None


class Conversation(BaseModel):
    system_prompt: Optional[str] = None
    tools: List[ChatCompletionToolParam] = Field(default_factory=list)
    # avoid mutable default here too
    turns: List[Turn] = Field(default_factory=list)

    def add_turn(self, turn: Optional[Turn] = None) -> Turn:
        if turn is None:
            turn = Turn()
        self.turns.append(turn)
        return turn

    def reset(self) -> None:
        self.turns = []

    def get_exchange_summary(self) -> str:
        """Generate a brief summary of the entire conversation."""
        summaries = []
        for turn in self.turns:
            response = {"user": "", "assistant": ""}
            user_query, assistant_response = turn.get_exchange() or (None, None)
            if user_query:
                response["user"] = user_query.message.content
            if assistant_response:
                response["assistant"] = assistant_response.message.content
            summaries.append(response)
        return summaries

    def write_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.model_dump(), indent=2))
