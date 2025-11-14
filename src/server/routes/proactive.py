"""Proactive chat routes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from ..dependencies import get_scheduler
from ..schemas import (
    ProactiveChatPendingResponse,
    ProactiveChatStatusResponse,
    ProactiveChatToggleRequest,
    ProactiveChatToggleResponse,
)

logger = logging.getLogger(__name__)


def register_proactive_routes(app: FastAPI) -> None:
    """Register proactive chat endpoints."""

    @app.post("/api/proactive-chat/toggle", response_model=ProactiveChatToggleResponse)
    async def toggle_proactive_chat(request: ProactiveChatToggleRequest) -> ProactiveChatToggleResponse:
        """Enable/disable proactive chat scheduling."""
        scheduler = get_scheduler()
        try:
            if request.enabled:
                scheduler.start()
            else:
                scheduler.stop()
            scheduler.set_enabled(request.enabled)
            return ProactiveChatToggleResponse(
                enabled=request.enabled,
                message="Proactive chat status updated",
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to toggle proactive chat: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/proactive-chat/status", response_model=ProactiveChatStatusResponse)
    async def get_proactive_chat_status() -> ProactiveChatStatusResponse:
        """Return scheduler runtime status."""
        scheduler = get_scheduler()
        try:
            status = scheduler.get_status()
            return ProactiveChatStatusResponse(**status)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            logger.exception("Failed to fetch proactive status: %s", exc)
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
