import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.ai_secretary.scheduler import ProactiveChatScheduler
from src.ai_secretary.prompt_templates import ProactivePromptManager
from src.ai_secretary.secretary import AISecretary

logger = logging.getLogger(__name__)


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


@lru_cache(maxsize=1)
def get_secretary() -> AISecretary:
    """Lazily create a singleton AISecretary instance."""
    return AISecretary()


@lru_cache(maxsize=1)
def get_scheduler() -> ProactiveChatScheduler:
    """Lazily create a singleton ProactiveChatScheduler instance."""
    secretary = get_secretary()
    templates_dir = Path(__file__).parent.parent.parent / "config" / "proactive_prompts"
    prompt_manager = ProactivePromptManager(templates_dir)
    scheduler = ProactiveChatScheduler(secretary, prompt_manager)
    scheduler.start()  # スケジューラーを起動
    return scheduler


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="AI Secretary API", version="1.0.0")

    # Allow local development frontends to communicate freely
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Simple health check endpoint."""
        return HealthResponse(status="ok")

    @app.get("/api/models", response_model=ModelsResponse)
    async def get_models() -> ModelsResponse:
        """Get available Ollama models."""
        secretary = get_secretary()
        try:
            models = await asyncio.to_thread(secretary.get_available_models)
            return ModelsResponse(models=models)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to get models: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """Handle chat requests by delegating to the AISecretary."""
        secretary = get_secretary()
        try:
            result = await asyncio.to_thread(
                secretary.chat,
                request.message,
                True,
                request.play_audio,
                request.model,
            )
            return ChatResponse(**result)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Chat request failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/proactive-chat/toggle", response_model=ProactiveChatToggleResponse)
    async def toggle_proactive_chat(
        request: ProactiveChatToggleRequest,
    ) -> ProactiveChatToggleResponse:
        """Enable or disable proactive chat."""
        scheduler = get_scheduler()
        try:
            if request.enabled:
                scheduler.enable()
                message = "Proactive chat enabled"
            else:
                scheduler.disable()
                message = "Proactive chat disabled"

            return ProactiveChatToggleResponse(enabled=request.enabled, message=message)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to toggle proactive chat: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/proactive-chat/status", response_model=ProactiveChatStatusResponse)
    async def get_proactive_chat_status() -> ProactiveChatStatusResponse:
        """Get current status of proactive chat."""
        scheduler = get_scheduler()
        try:
            status = scheduler.get_status()
            return ProactiveChatStatusResponse(**status)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to get proactive chat status: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/proactive-chat/pending", response_model=ProactiveChatPendingResponse)
    async def get_pending_proactive_messages() -> ProactiveChatPendingResponse:
        """Get pending proactive messages (clears queue after retrieval)."""
        scheduler = get_scheduler()
        try:
            messages = scheduler.get_pending_messages()
            return ProactiveChatPendingResponse(messages=messages)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to get pending messages: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
