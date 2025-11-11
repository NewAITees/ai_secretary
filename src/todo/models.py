from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TodoStatus(str, Enum):
    """単純なTodoステータス。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass(slots=True)
class TodoItem:
    """永続化済みTodoアイテムの表現。"""

    id: int
    title: str
    description: str
    status: TodoStatus
    due_date: Optional[str]
    created_at: str
    updated_at: str
