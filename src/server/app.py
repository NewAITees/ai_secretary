import asyncio
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


@lru_cache(maxsize=1)
def get_secretary() -> AISecretary:
    """Lazily create a singleton AISecretary instance."""
    return AISecretary()


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

    return app


app = create_app()
