"""Bash approval routes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from ..dependencies import get_bash_approval_queue
from ..schemas import BashApprovalResponse, BashPendingResponse

logger = logging.getLogger(__name__)


def register_bash_routes(app: FastAPI) -> None:
    """Register approval endpoints for bash commands."""

    @app.get("/api/bash/pending", response_model=BashPendingResponse)
    async def get_pending_bash_approvals() -> BashPendingResponse:
        """Get pending bash command approval requests."""
        queue = get_bash_approval_queue()
        try:
            requests = queue.get_pending_requests()
            return BashPendingResponse(requests=requests)
        except Exception as exc:
            logger.exception("Failed to get pending bash approvals: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to get pending approvals"
            ) from exc

    @app.post("/api/bash/approve/{request_id}", response_model=BashApprovalResponse)
    async def approve_bash_command(request_id: str, approved: bool) -> BashApprovalResponse:
        """Approve or reject a bash command execution request."""
        queue = get_bash_approval_queue()
        try:
            if approved:
                success = queue.approve(request_id)
                message = "Command approved" if success else "Request not found"
            else:
                success = queue.reject(request_id)
                message = "Command rejected" if success else "Request not found"

            if not success:
                raise HTTPException(status_code=404, detail="Request not found")

            return BashApprovalResponse(approved=approved, message=message)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to approve/reject bash command: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to process approval"
            ) from exc
