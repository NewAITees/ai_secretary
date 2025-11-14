"""Pydantic schemas for the FastAPI server."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.todo import TodoStatus


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str = Field(..., description="User message to send to the AI secretary")
    play_audio: bool = Field(
        default=True,
        description="If true, synthesized audio will be played immediately on the server",
    )
    model: Optional[str] = Field(
        default=None,
        description="Ollama model name to use for this request (if not specified, uses default)",
    )


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    voice_plan: Optional[Dict[str, Any]] = Field(
        default=None, description="Planned COEIROINK payload"
    )
    audio_path: Optional[str] = Field(
        default=None, description="Path of the synthesized audio file (if generated)"
    )
    played_audio: bool = Field(
        default=False,
        description="Indicates whether the audio was played on the server side",
    )
    raw_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Original JSON payload returned by Ollama"
    )


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: str


class ModelsResponse(BaseModel):
    """Response for models list endpoint."""

    models: list[str]


class ProactiveChatToggleRequest(BaseModel):
    """Request body for proactive chat toggle endpoint."""

    enabled: bool = Field(..., description="Enable or disable proactive chat")


class ProactiveChatToggleResponse(BaseModel):
    """Response for proactive chat toggle endpoint."""

    enabled: bool
    message: str


class ProactiveChatStatusResponse(BaseModel):
    """Response for proactive chat status endpoint."""

    enabled: bool
    running: bool
    interval_seconds: int
    pending_count: int


class ProactiveChatMessage(BaseModel):
    """Single proactive chat message."""

    text: str
    timestamp: float
    details: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None
    error: Optional[bool] = False


class ProactiveChatPendingResponse(BaseModel):
    """Response for pending proactive messages endpoint."""

    messages: List[ProactiveChatMessage]


class ChatSessionSummary(BaseModel):
    """Chat session metadata for listing/search results."""

    session_id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int


class ChatSessionDetail(ChatSessionSummary):
    """Chat session with the full message log."""

    messages: List[Dict[str, Any]]


class ChatLoadRequest(BaseModel):
    """Request body for loading a chat session."""

    session_id: str = Field(..., description="チャットセッションID（UUID形式）")


class TodoResponse(BaseModel):
    """Serialized todo item."""

    id: int
    title: str
    description: str
    status: TodoStatus
    due_date: Optional[date] = None
    created_at: str
    updated_at: str

    class Config:
        use_enum_values = True


class TodoCreateRequest(BaseModel):
    """Request body for creating todo."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    due_date: Optional[date] = Field(default=None, description="ISO date (YYYY-MM-DD)")
    status: TodoStatus = Field(default=TodoStatus.PENDING)


class TodoUpdateRequest(BaseModel):
    """Request body for updating todo."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_date: Optional[date] = Field(default=None)
    status: Optional[TodoStatus] = Field(default=None)


class BashApprovalRequest(BaseModel):
    """Bash command approval request."""

    request_id: str
    command: str
    reason: str
    timestamp: float


class BashApprovalResponse(BaseModel):
    """Response for bash approval endpoint."""

    approved: bool
    message: str


class BashPendingResponse(BaseModel):
    """Response for pending bash approvals."""

    requests: List[BashApprovalRequest]
