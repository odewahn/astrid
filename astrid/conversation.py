from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any

from litellm.utils import Message, Usage


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


class Conversation(BaseModel):
    system_prompt: Optional[str] = None
    # avoid mutable default here too
    turns: List[Turn] = Field(default_factory=list)
