"""Dependency helpers shared across FastAPI routes."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import List

from src.ai_secretary.config import Config
from src.ai_secretary.logger import setup_logger
from src.ai_secretary.prompt_templates import ProactivePromptManager
from src.ai_secretary.scheduler import ProactiveChatScheduler
from src.ai_secretary.secretary import AISecretary
from src.chat_history import ChatHistoryRepository
from src.todo import TodoItem, TodoRepository, UNSET

from .approval_queue import BashApprovalQueue
from .schemas import (
    ChatSessionDetail,
    ChatSessionSummary,
    TodoResponse,
)

config = Config.from_yaml()
setup_logger(log_level=config.log_level, log_file=config.log_file)


@lru_cache(maxsize=1)
def get_secretary() -> AISecretary:
    """Lazily create a singleton AISecretary instance."""
    return AISecretary()


@lru_cache(maxsize=1)
def get_scheduler() -> ProactiveChatScheduler:
    """Lazily create a singleton ProactiveChatScheduler instance."""
    secretary = get_secretary()
    templates_dir = Path(__file__).parent.parent / "config" / "proactive_prompts"
    prompt_manager = ProactivePromptManager(templates_dir)
    scheduler = ProactiveChatScheduler(
        secretary,
        prompt_manager,
        interval_seconds=config.proactive_chat.interval_seconds,
        max_queue_size=config.proactive_chat.max_queue_size,
    )
    scheduler.start()
    return scheduler


@lru_cache(maxsize=1)
def get_todo_repository() -> TodoRepository:
    """Singleton TodoRepository."""
    return TodoRepository()


@lru_cache(maxsize=1)
def get_bash_approval_queue() -> BashApprovalQueue:
    """Singleton BashApprovalQueue."""
    return BashApprovalQueue()


@lru_cache(maxsize=1)
def get_chat_history_repository() -> ChatHistoryRepository:
    """Singleton ChatHistoryRepository."""
    return ChatHistoryRepository()


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


def serialize_chat_session_summary(session) -> ChatSessionSummary:
    """Convert ChatSession dataclass to summary model."""
    messages = session.messages
    return ChatSessionSummary(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(messages),
    )


def serialize_chat_session_detail(session) -> ChatSessionDetail:
    """Convert ChatSession dataclass to detail model."""
    messages = session.messages
    return ChatSessionDetail(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(messages),
        messages=messages,
    )


def build_detail_from_secretary(secretary: AISecretary) -> ChatSessionDetail:
    """Build a ChatSessionDetail from the in-memory secretary state."""
    messages = secretary.conversation_history
    title = secretary.session_title or "新規セッション"
    return ChatSessionDetail(
        session_id=secretary.session_id,
        title=title,
        created_at=None,
        updated_at=None,
        message_count=len(messages),
        messages=messages,
    )
