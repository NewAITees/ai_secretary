import asyncio
import logging
import threading
import uuid
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.ai_secretary.config import Config
from src.ai_secretary.scheduler import ProactiveChatScheduler
from src.ai_secretary.prompt_templates import ProactivePromptManager
from src.ai_secretary.secretary import AISecretary
from src.todo import TodoItem, TodoRepository, TodoStatus, UNSET

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
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    due_date: Optional[date] = Field(default=None, description="ISO date (YYYY-MM-DD)")
    status: TodoStatus = Field(default=TodoStatus.PENDING)


class TodoUpdateRequest(BaseModel):
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
                "timestamp": asyncio.get_event_loop().time(),
            }
            self._events[request_id] = threading.Event()
        logger.info(f"Approval request added: {request_id}")
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
        logger.info(f"Request approved: {request_id}")
        return True

    def reject(self, request_id: str) -> bool:
        """Reject a request. Returns True if request was found."""
        with self._lock:
            if request_id not in self._requests:
                return False
            self._requests[request_id]["approved"] = False
            if request_id in self._events:
                self._events[request_id].set()
        logger.info(f"Request rejected: {request_id}")
        return True

    def wait_for_approval(self, request_id: str, timeout: float = 300.0) -> bool:
        """Wait for approval decision. Returns True if approved, False if rejected or timeout."""
        event = self._events.get(request_id)
        if not event:
            return False

        event.wait(timeout=timeout)

        with self._lock:
            if request_id not in self._requests:
                return False
            approved = self._requests[request_id].get("approved", False)
            # Clean up after decision
            del self._requests[request_id]
            del self._events[request_id]

        return approved


@lru_cache(maxsize=1)
def get_secretary() -> AISecretary:
    """Lazily create a singleton AISecretary instance."""
    return AISecretary()


@lru_cache(maxsize=1)
def get_scheduler() -> ProactiveChatScheduler:
    """Lazily create a singleton ProactiveChatScheduler instance."""
    config = Config.from_yaml()
    secretary = get_secretary()
    templates_dir = Path(__file__).parent.parent.parent / "config" / "proactive_prompts"
    prompt_manager = ProactivePromptManager(templates_dir)
    scheduler = ProactiveChatScheduler(
        secretary,
        prompt_manager,
        interval_seconds=config.proactive_chat.interval_seconds,
        max_queue_size=config.proactive_chat.max_queue_size,
    )
    scheduler.start()  # スケジューラーを起動
    return scheduler


@lru_cache(maxsize=1)
def get_todo_repository() -> TodoRepository:
    """Singleton TodoRepository."""
    return TodoRepository()


@lru_cache(maxsize=1)
def get_bash_approval_queue() -> BashApprovalQueue:
    """Singleton BashApprovalQueue."""
    return BashApprovalQueue()


def serialize_todo(item: TodoItem) -> TodoResponse:
    """Convert domain TodoItem to API response."""
    due_date_value = None
    if item.due_date:
        try:
            due_date_value = date.fromisoformat(item.due_date)
        except ValueError:
            due_date_value = None
    return TodoResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        status=item.status,
        due_date=due_date_value,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


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

    @app.get("/api/todos", response_model=List[TodoResponse])
    async def list_todos() -> List[TodoResponse]:
        """List todos ordered by status/due date."""
        repo = get_todo_repository()
        try:
            todos = await asyncio.to_thread(repo.list)
            return [serialize_todo(todo) for todo in todos]
        except Exception as exc:
            logger.exception("Failed to list todos: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to list todos") from exc

    @app.post("/api/todos", response_model=TodoResponse)
    async def create_todo(request: TodoCreateRequest) -> TodoResponse:
        """Create a new todo."""
        repo = get_todo_repository()
        try:
            todo = await asyncio.to_thread(
                repo.create,
                request.title,
                request.description or "",
                request.due_date.isoformat() if request.due_date else None,
                request.status,
            )
            return serialize_todo(todo)
        except Exception as exc:
            logger.exception("Failed to create todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to create todo") from exc

    @app.patch("/api/todos/{todo_id}", response_model=TodoResponse)
    async def update_todo(todo_id: int, request: TodoUpdateRequest) -> TodoResponse:
        """Update an existing todo."""
        repo = get_todo_repository()
        try:
            payload = request.model_dump(exclude_unset=True)
            todo = await asyncio.to_thread(
                repo.update,
                todo_id,
                title=payload.get("title"),
                description=payload.get("description"),
                due_date=payload["due_date"].isoformat()
                if "due_date" in payload and payload["due_date"] is not None
                else (None if "due_date" in payload else UNSET),
                status=payload.get("status"),
            )
            if not todo:
                raise HTTPException(status_code=404, detail="Todo not found")
            return serialize_todo(todo)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to update todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to update todo") from exc

    @app.delete("/api/todos/{todo_id}")
    async def delete_todo(todo_id: int) -> Dict[str, bool]:
        """Delete a todo."""
        repo = get_todo_repository()
        try:
            deleted = await asyncio.to_thread(repo.delete, todo_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Todo not found")
            return {"deleted": True}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to delete todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to delete todo") from exc

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

    return app


app = create_app()
