from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SuggestRequest(BaseModel):
    draft: str = Field(min_length=1, max_length=8000)
    similar_prompts: list[str] = []
    recent_messages: list[ChatMessage] = []
    site: str = "chatgpt"


class SuggestResponse(BaseModel):
    suggestion_id: str
    score: float
    show_suggestion: bool
    missing: list[str]
    suggestions: list[str]
    conflicts: list[str] = []


class FeedbackRequest(BaseModel):
    suggestion_id: str
    action: Literal["accepted", "edited", "dismissed"]
