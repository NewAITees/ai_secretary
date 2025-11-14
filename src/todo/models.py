from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TodoStatus(str, Enum):
    """単純なTodoステータス。統合スキーマ対応版。"""

    TODO = "todo"  # 旧: pending
    DOING = "doing"  # 旧: in_progress
    DONE = "done"
    ARCHIVED = "archived"  # 新規追加

    # 後方互換性のためのエイリアス
    PENDING = "todo"
    IN_PROGRESS = "doing"


@dataclass(slots=True)
class TodoItem:
    """永続化済みTodoアイテムの表現。統合スキーマ対応版。"""

    id: int
    title: str
    description: str
    status: TodoStatus
    due_date: Optional[str]
    created_at: str
    updated_at: str
    priority: int = 3  # 1(高)～5(低)、デフォルト3
    tags_json: str = "[]"  # JSON形式のタグ配列
