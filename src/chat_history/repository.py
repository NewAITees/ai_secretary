"""Chat History Repository

チャット履歴のCRUD操作を提供するリポジトリクラス。
統合スキーマ（data/ai_secretary.db）を使用。

Design Reference: plan/P3_CHAT_HISTORY_PLAN_v2.md
Related Classes: ChatSession (models.py)
"""

from __future__ import annotations

import sqlite3
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import ChatSession


class ChatHistoryRepository:
    """SQLiteベースのチャット履歴管理。統合スキーマ対応版。"""

    def __init__(self, db_path: Optional[Path] = None):
        root = Path(__file__).resolve().parents[2]
        default_path = root / "data" / "ai_secretary.db"  # 統合DBパス
        env_path = os.getenv("AI_SECRETARY_DB_PATH")
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
        """統合スキーマでの初期化（chat_historyテーブル使用）"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    messages_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_updated ON chat_history(updated_at DESC)"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> ChatSession:
        return ChatSession(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            messages_json=row["messages_json"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_session(
        self, session_id: str, title: str, messages: List[Dict[str, Any]]
    ) -> ChatSession:
        """新規チャットセッションを作成

        Args:
            session_id: セッションID（UUID推奨）
            title: セッションのタイトル
            messages: メッセージ配列 [{"role": "user", "content": "..."}, ...]

        Returns:
            作成されたChatSessionオブジェクト

        Raises:
            sqlite3.IntegrityError: session_idが重複している場合
        """
        now = self._now()
        messages_json = json.dumps(messages, ensure_ascii=False)

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_history (session_id, title, messages_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, title, messages_json, now, now),
            )
            conn.commit()
            session_pk = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM chat_history WHERE id = ?", (session_pk,)
            ).fetchone()
        return self._row_to_session(row)

    def update_session(
        self, session_id: str, messages: List[Dict[str, Any]], title: Optional[str] = None
    ) -> Optional[ChatSession]:
        """既存セッションのメッセージ履歴を更新

        Args:
            session_id: セッションID
            messages: 更新後のメッセージ配列
            title: タイトル（指定時のみ更新）

        Returns:
            更新後のChatSessionオブジェクト、存在しない場合はNone
        """
        messages_json = json.dumps(messages, ensure_ascii=False)
        now = self._now()

        with self._connect() as conn:
            if title:
                conn.execute(
                    """
                    UPDATE chat_history
                    SET messages_json = ?, title = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (messages_json, title, now, session_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE chat_history
                    SET messages_json = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (messages_json, now, session_id),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM chat_history WHERE session_id = ?", (session_id,)
            ).fetchone()

        return self._row_to_session(row) if row else None

    def save_or_update(
        self, session_id: str, title: str, messages: List[Dict[str, Any]]
    ) -> ChatSession:
        """セッションが存在しなければ作成、存在すれば更新

        Args:
            session_id: セッションID
            title: セッションのタイトル
            messages: メッセージ配列

        Returns:
            保存/更新されたChatSessionオブジェクト
        """
        existing = self.get_session(session_id)
        if existing:
            return self.update_session(session_id, messages, title)
        else:
            return self.create_session(session_id, title, messages)

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """セッションIDでセッションを取得

        Args:
            session_id: セッションID

        Returns:
            ChatSessionオブジェクト、存在しない場合はNone
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chat_history WHERE session_id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def list_sessions(self, limit: int = 20) -> List[ChatSession]:
        """セッション一覧を取得（新しい順）

        Args:
            limit: 取得する最大件数

        Returns:
            ChatSessionオブジェクトのリスト
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_history
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def search_sessions(self, query: str, limit: int = 20) -> List[ChatSession]:
        """タイトルまたはメッセージ内容で検索

        Args:
            query: 検索キーワード
            limit: 取得する最大件数

        Returns:
            ChatSessionオブジェクトのリスト
        """
        search_pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_history
                WHERE title LIKE ? OR messages_json LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (search_pattern, search_pattern, limit),
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        """セッションを削除

        Args:
            session_id: セッションID

        Returns:
            削除成功時True、セッションが存在しない場合False
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM chat_history WHERE session_id = ?", (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
