"""Validated public API inputs."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    provider: Literal["ollama", "gemini"] = "ollama"
    unit: Literal[1, 2, 3] | None = None
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=96, ge=1, le=2048)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=12)
    exercise_id: str | None = Field(default=None, pattern=r"^U[123]-[A-Z0-9-]+$", max_length=100)
    attempt: str | None = Field(default=None, min_length=1, max_length=1500, pattern=r"\S")

    @model_validator(mode="after")
    def complete_pairs(self):
        if len(self.history) % 2 or any(
            entry.role != ("user" if index % 2 == 0 else "assistant")
            or not entry.content.strip()
            for index, entry in enumerate(self.history)
        ):
            raise ValueError("History must contain ordered, complete user/assistant pairs.")
        return self


class SpeechLogRequest(BaseModel):
    human: str = Field(min_length=1, max_length=4000)
    assistant: str = Field(min_length=1, max_length=8000)
    provider: Literal["ollama", "gemini"] = "ollama"
    model: str | None = Field(default=None, max_length=200)
    unit: Literal[1, 2, 3] | None = None
