from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class ConversationContextMessage(BaseModel):
    role: Literal["user", "assistant", "error"]
    content: str


class ChatRequest(BaseModel):
    query: str
    answer_detail: Literal["brief", "detailed"] = "brief"
    conversation_id: str | None = None
    conversation_context: list[ConversationContextMessage] = Field(
        default_factory=list
    )


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=120,
    )
    pinned: bool | None = None
