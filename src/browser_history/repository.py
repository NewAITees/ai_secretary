"""Browser history repository for CRUD operations."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import BrowserHistoryEntry


class BrowserHistoryRepository:
    """
    ブラウザ履歴リポジトリ

    統合DB（data/ai_secretary.db）のbrowser_historyテーブルを操作します。
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: データベースファイルパス（Noneの場合はデフォルト）
        """
        root = Path(__file__).resolve().parents[2]
        default_path = root / "data" / "ai_secretary.db"
        env_path = os.getenv("AI_SECRETARY_DB_PATH")

        if db_path:
            self.db_path = Path(db_path)
        elif env_path:
            self.db_path = Path(env_path)
        else:
            self.db_path = default_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        """データベース接続を作成"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """テーブルを作成（存在しない場合）"""
        with self._connect() as conn:
            # browser_historyテーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    visit_time TEXT NOT NULL,
                    visit_count INTEGER DEFAULT 1,
                    transition_type INTEGER,
                    source_browser TEXT DEFAULT 'brave',
                    imported_at TEXT NOT NULL,
                    brave_url_id INTEGER,
                    brave_visit_id INTEGER
                )
                """
            )

            # インデックス作成
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_browser_history_url
                ON browser_history(url)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_browser_history_visit_time
                ON browser_history(visit_time DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_browser_history_title
                ON browser_history(title)
                """
            )

            # 重複排除用のユニークインデックス（source_browser + brave_visit_id）
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_browser_history_unique_visit
                ON browser_history(source_browser, brave_visit_id)
                WHERE brave_visit_id IS NOT NULL
                """
            )

            # browser_import_logテーブル
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_import_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    record_count INTEGER,
                    last_visit_time TEXT,
                    status TEXT DEFAULT 'success'
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_import_log_source
                ON browser_import_log(source_path)
                """
            )

            conn.commit()

    def add_entry(self, entry: BrowserHistoryEntry) -> Optional[BrowserHistoryEntry]:
        """
        履歴エントリを追加（重複は無視）

        Args:
            entry: 追加するエントリ

        Returns:
            IDが設定されたエントリ（重複の場合None）
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO browser_history (
                        url, title, visit_time, visit_count,
                        transition_type, source_browser, imported_at,
                        brave_url_id, brave_visit_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.url,
                        entry.title,
                        entry.visit_time.isoformat(),
                        entry.visit_count,
                        entry.transition_type,
                        entry.source_browser,
                        now,
                        entry.brave_url_id,
                        entry.brave_visit_id,
                    ),
                )
                entry.id = cursor.lastrowid
                entry.imported_at = datetime.fromisoformat(now)
                conn.commit()
                return entry
            except sqlite3.IntegrityError:
                # 重複エントリは無視
                conn.rollback()
                return None

    def get_entry(self, entry_id: int) -> Optional[BrowserHistoryEntry]:
        """
        IDで履歴エントリを取得

        Args:
            entry_id: エントリID

        Returns:
            エントリ（存在しない場合None）
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM browser_history WHERE id = ?", (entry_id,)
            ).fetchone()

        if not row:
            return None

        return self._row_to_entry(row)

    def list_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        url_pattern: Optional[str] = None,
        limit: int = 100,
    ) -> List[BrowserHistoryEntry]:
        """
        履歴を取得

        Args:
            start_date: 開始日（YYYY-MM-DD形式）
            end_date: 終了日（YYYY-MM-DD形式）
            url_pattern: URLパターン（LIKE検索）
            limit: 取得件数上限

        Returns:
            履歴エントリのリスト（新しい順）
        """
        query = "SELECT * FROM browser_history WHERE 1=1"
        params = []

        if start_date:
            query += " AND visit_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND visit_time <= ?"
            params.append(f"{end_date}T23:59:59")

        if url_pattern:
            query += " AND url LIKE ?"
            params.append(f"%{url_pattern}%")

        query += " ORDER BY visit_time DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def search_history(self, query: str, limit: int = 50) -> List[BrowserHistoryEntry]:
        """
        履歴を検索（URL/タイトル）

        Args:
            query: 検索クエリ
            limit: 取得件数上限

        Returns:
            マッチした履歴エントリのリスト
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM browser_history
                WHERE url LIKE ? OR title LIKE ?
                ORDER BY visit_time DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()

        return [self._row_to_entry(row) for row in rows]

    def delete_old_entries(self, before_date: str) -> int:
        """
        指定日時より古いエントリを削除

        Args:
            before_date: この日時より前のエントリを削除（YYYY-MM-DD形式）

        Returns:
            削除件数
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM browser_history WHERE visit_time < ?", (before_date,)
            )
            deleted_count = cursor.rowcount
            conn.commit()

        return deleted_count

    def log_import(
        self, source_path: str, record_count: int, last_visit_time: Optional[str] = None
    ) -> None:
        """
        インポートログを記録

        Args:
            source_path: インポート元パス
            record_count: インポート件数
            last_visit_time: 最新の訪問時刻
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO browser_import_log (
                    source_path, imported_at, record_count, last_visit_time, status
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source_path, now, record_count, last_visit_time, "success"),
            )
            conn.commit()

    def _row_to_entry(self, row: sqlite3.Row) -> BrowserHistoryEntry:
        """SQLiteの行をBrowserHistoryEntryに変換"""
        return BrowserHistoryEntry(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            visit_time=datetime.fromisoformat(row["visit_time"]),
            visit_count=row["visit_count"],
            transition_type=row["transition_type"],
            source_browser=row["source_browser"],
            brave_url_id=row["brave_url_id"],
            brave_visit_id=row["brave_visit_id"],
            imported_at=datetime.fromisoformat(row["imported_at"]),
        )
