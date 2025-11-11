from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Any

from .models import TodoItem, TodoStatus

UNSET = object()


class TodoRepository:
    """SQLiteベースのTODO管理。"""

    def __init__(self, db_path: Optional[Path] = None):
        root = Path(__file__).resolve().parents[2]
        default_path = root / "data" / "todo.db"
        env_path = os.getenv("AI_SECRETARY_TODO_DB_PATH")
        if db_path:
            self.db_path = Path(db_path)
        elif env_path:
            self.db_path = Path(env_path)
        else:
            self.db_path = default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_todos_status_due ON todos (status, due_date)"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> TodoItem:
        return TodoItem(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TodoStatus(row["status"]),
            due_date=row["due_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list(self) -> list[TodoItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM todos
                ORDER BY
                    CASE status
                        WHEN 'done' THEN 1
                        ELSE 0
                    END,
                    COALESCE(due_date, ''),
                    id DESC
                """
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def create(
        self,
        title: str,
        description: str = "",
        due_date: Optional[str] = None,
        status: TodoStatus = TodoStatus.PENDING,
    ) -> TodoItem:
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO todos (title, description, status, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (title, description, status.value, due_date, now, now),
            )
            conn.commit()
            todo_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return self._row_to_item(row)

    def update(
        self,
        todo_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Any = UNSET,
        status: Optional[TodoStatus] = None,
    ) -> Optional[TodoItem]:
        fields: list[str] = []
        params: list[object] = []

        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if due_date is not UNSET:
            fields.append("due_date = ?")
            params.append(due_date)
        if status is not None:
            fields.append("status = ?")
            params.append(status.value)

        if not fields:
            return self.get(todo_id)

        fields.append("updated_at = ?")
        params.append(self._now())
        params.append(todo_id)

        with self._connect() as conn:
            conn.execute(f"UPDATE todos SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()

        return self._row_to_item(row) if row else None

    def delete(self, todo_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get(self, todo_id: int) -> Optional[TodoItem]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def bulk_create(self, items: Iterable[dict]) -> list[TodoItem]:
        """テスト/初期データ投入用のヘルパー。"""
        created: List[TodoItem] = []
        for item in items:
            created.append(
                self.create(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    due_date=item.get("due_date"),
                    status=TodoStatus(item.get("status", TodoStatus.PENDING.value)),
                )
            )
        return created
