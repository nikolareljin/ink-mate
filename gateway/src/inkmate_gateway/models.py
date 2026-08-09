from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Card(StrictModel):
    kind: Literal["home", "answer", "tools", "capture", "status", "confirmation", "offline", "error"]
    title: str = Field(max_length=32)
    body: str = Field(max_length=240)
    footer: str = Field(default="", max_length=48)
    continuation: bool = False
    severity: Literal["normal", "notice", "warning", "critical"] = "normal"
    updated_at: datetime = Field(default_factory=utcnow)


class ActionProposal(StrictModel):
    request_id: str
    action: str = Field(max_length=64)
    target: str = Field(max_length=160)
    expires_at: datetime


class ErrorDetail(StrictModel):
    code: str
    message: str = Field(max_length=240)
    retryable: bool


class InteractionResponse(StrictModel):
    protocol_version: Literal[1] = 1
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,64}$")
    timestamp: datetime = Field(default_factory=utcnow)
    transcript: str = Field(max_length=4096)
    card: Card
    speech_url: str | None = None
    pending_action: ActionProposal | None = None
    error: ErrorDetail | None = None


class Snapshot(StrictModel):
    protocol_version: Literal[1] = 1
    device_id: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,64}$")
    timestamp: datetime = Field(default_factory=utcnow)
    cards: list[Card] = Field(max_length=8)
    gateway: dict[str, str | int | float | bool | None]


class ActionResult(StrictModel):
    request_id: str
    status: Literal["executed", "cancelled"]
    output: str | None = None


class WorkItem(StrictModel):
    """A reviewable, local-first result of a voice capture."""

    id: str = Field(pattern=r"^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$")
    project: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(max_length=600)
    next_steps: list[str] = Field(default_factory=list, max_length=5)
    path: str = Field(max_length=512)
    issue_url: str | None = None
