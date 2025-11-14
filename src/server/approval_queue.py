"""Thread-safe queue for bash command approvals."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Dict, List

from .schemas import BashApprovalRequest

logger = logging.getLogger(__name__)


class BashApprovalQueue:
    """Thread-safe queue for bash approval requests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, Dict[str, Any]] = {}
        self._events: Dict[str, threading.Event] = {}

    def add_request(self, command: str, reason: str) -> str:
        """Add a new approval request and return request ID."""
        request_id = str(uuid.uuid4())
        with self._lock:
            self._requests[request_id] = {
                "command": command,
                "reason": reason,
                "timestamp": time.time(),
            }
            self._events[request_id] = threading.Event()
        logger.info("Approval request added: %s", request_id)
        return request_id

    def get_pending_requests(self) -> List[BashApprovalRequest]:
        """Get all pending approval requests."""
        with self._lock:
            return [
                BashApprovalRequest(
                    request_id=req_id,
                    command=req["command"],
                    reason=req["reason"],
                    timestamp=req["timestamp"],
                )
                for req_id, req in self._requests.items()
            ]

    def approve(self, request_id: str) -> bool:
        """Approve a request. Returns True if request was found."""
        with self._lock:
            if request_id not in self._requests:
                return False
            self._requests[request_id]["approved"] = True
            if request_id in self._events:
                self._events[request_id].set()
        logger.info("Request approved: %s", request_id)
        return True

    def reject(self, request_id: str) -> bool:
        """Reject a request. Returns True if request was found."""
        with self._lock:
            if request_id not in self._requests:
                return False
            self._requests[request_id]["approved"] = False
            if request_id in self._events:
                self._events[request_id].set()
        logger.info("Request rejected: %s", request_id)
        return True

    def wait_for_approval(self, request_id: str, timeout: float = 300.0) -> bool:
        """Wait for approval decision. Returns True if approved, False otherwise."""
        event = self._events.get(request_id)
        if not event:
            return False

        event.wait(timeout=timeout)

        with self._lock:
            if request_id not in self._requests:
                return False
            approved = self._requests[request_id].get("approved", False)
            del self._requests[request_id]
            del self._events[request_id]

        return approved
