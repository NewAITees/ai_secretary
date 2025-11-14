from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Any

from .models import TodoItem, TodoStatus

UNSET = object()


class TodoRepository:
    """SQLiteベースのTODO管理。統合スキーマ対応版。"""

    def __init__(self, db_path: Optional[Path] = None):
        root = Path(__file__).resolve().parents[2]
        default_path = root / "data" / "ai_secretary.db"  # 統合DBパスに変更
        env_path = os.getenv("AI_SECRETARY_DB_PATH")  # 環境変数名も変更
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
        """統合スキーマでの初期化（todo_itemsテーブル使用）"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS todo_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL CHECK (status IN ('todo','doing','done','archived')),
                    priority INTEGER NOT NULL DEFAULT 3,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    due_date TEXT,
                    tags_json TEXT DEFAULT '[]'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_todo_status ON todo_items(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_todo_priority ON todo_items(priority)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_todo_due ON todo_items(due_date)")
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
            priority=row["priority"],
            tags_json=row["tags_json"],
        )

    def list(self) -> list[TodoItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM todo_items
                ORDER BY
                    priority ASC,
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
        status: TodoStatus = TodoStatus.TODO,
        priority: int = 3,
        tags_json: str = "[]",
    ) -> TodoItem:
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO todo_items (title, description, status, due_date, created_at, updated_at, priority, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, description, status.value, due_date, now, now, priority, tags_json),
            )
            conn.commit()
            todo_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (todo_id,)).fetchone()
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
            conn.execute(f"UPDATE todo_items SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (todo_id,)).fetchone()

        return self._row_to_item(row) if row else None

    def delete(self, todo_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM todo_items WHERE id = ?", (todo_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get(self, todo_id: int) -> Optional[TodoItem]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM todo_items WHERE id = ?", (todo_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def bulk_create(self, items: Iterable[dict]) -> list[TodoItem]:
        """テスト/初期データ投入用のヘルパー。"""
        from typing import List
        created: List[TodoItem] = []
        for item in items:
            created.append(
                self.create(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    due_date=item.get("due_date"),
                    status=TodoStatus(item.get("status", TodoStatus.TODO.value)),
                    priority=item.get("priority", 3),
                    tags_json=item.get("tags_json", "[]"),
                )
            )
        return created
