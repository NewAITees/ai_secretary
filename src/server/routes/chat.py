"""Chat-related API routes."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException

from ..dependencies import (
    build_detail_from_secretary,
    get_chat_history_repository,
    get_secretary,
    serialize_chat_session_detail,
    serialize_chat_session_summary,
)
from ..schemas import (
    ChatLoadRequest,
    ChatRequest,
    ChatResponse,
    ChatSessionDetail,
    ChatSessionSummary,
    HealthResponse,
    ModelsResponse,
)

logger = logging.getLogger(__name__)


def register_chat_routes(app: FastAPI) -> None:
    """Register chat/session endpoints on the provided app."""

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

    @app.get("/api/chat/sessions", response_model=List[ChatSessionSummary])
    async def list_chat_sessions(
        limit: int = 20, query: Optional[str] = None
    ) -> List[ChatSessionSummary]:
        """List chat sessions ordered by updated timestamp."""
        repo = get_chat_history_repository()
        try:
            if query:
                sessions = await asyncio.to_thread(repo.search_sessions, query, limit)
            else:
                sessions = await asyncio.to_thread(repo.list_sessions, limit)
            return [serialize_chat_session_summary(session) for session in sessions]
        except Exception as exc:
            logger.exception("Failed to list chat sessions: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to list chat sessions"
            ) from exc

    @app.get("/api/chat/sessions/{session_id}", response_model=ChatSessionDetail)
    async def get_chat_session(session_id: str) -> ChatSessionDetail:
        """Fetch a single chat session."""
        repo = get_chat_history_repository()
        try:
            session = await asyncio.to_thread(repo.get_session, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return serialize_chat_session_detail(session)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to fetch chat session %s: %s", session_id, exc)
            raise HTTPException(
                status_code=500, detail="Failed to fetch chat session"
            ) from exc

    @app.get("/api/chat/session/current", response_model=ChatSessionDetail)
    async def get_current_chat_session() -> ChatSessionDetail:
        """Return the currently active chat session."""
        secretary = get_secretary()
        repo = get_chat_history_repository()
        try:
            session = await asyncio.to_thread(repo.get_session, secretary.session_id)
            if session:
                return serialize_chat_session_detail(session)
            return build_detail_from_secretary(secretary)
        except Exception as exc:
            logger.exception("Failed to fetch current chat session: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to fetch current chat session"
            ) from exc

    @app.post("/api/chat/load", response_model=ChatSessionDetail)
    async def load_chat_session(request: ChatLoadRequest) -> ChatSessionDetail:
        """Load an existing chat session into the secretary."""
        secretary = get_secretary()
        repo = get_chat_history_repository()
        try:
            loaded = await asyncio.to_thread(secretary.load_session, request.session_id)
            if not loaded:
                raise HTTPException(status_code=404, detail="Session not found")
            session = await asyncio.to_thread(repo.get_session, request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return serialize_chat_session_detail(session)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to load chat session %s: %s", request.session_id, exc)
            raise HTTPException(status_code=500, detail="Failed to load session") from exc

    @app.post("/api/chat/reset", response_model=ChatSessionDetail)
    async def reset_chat_session() -> ChatSessionDetail:
        """Reset the in-memory conversation and return its initial state."""
        secretary = get_secretary()
        try:
            await asyncio.to_thread(secretary.reset_conversation)
            return build_detail_from_secretary(secretary)
        except Exception as exc:
            logger.exception("Failed to reset chat session: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to reset session") from exc
