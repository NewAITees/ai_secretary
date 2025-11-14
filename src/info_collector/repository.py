"""
情報収集データのリポジトリ層

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - データモデル
- src/info_collector/collectors/ - データ収集器
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from .models import CollectedInfo, InfoSummary


class InfoCollectorRepository:
    """情報収集データのCRUD操作を提供するリポジトリ"""

    def __init__(self, db_path: str = "data/ai_secretary.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_tables()

    def _ensure_db_directory(self) -> None:
        """DBディレクトリの存在確認・作成"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_tables(self) -> None:
        """テーブル初期化（存在しない場合のみ作成）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collected_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT,
                    snippet TEXT,
                    published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    source_name TEXT,
                    metadata_json TEXT,
                    UNIQUE(source_type, url)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_source_type
                ON collected_info(source_type)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_fetched_at
                ON collected_info(fetched_at DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_info_published_at
                ON collected_info(published_at DESC)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS info_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    source_info_ids TEXT,
                    created_at TEXT NOT NULL,
                    query TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_summary_created_at
                ON info_summaries(created_at DESC)
                """
            )

    def add_info(self, info: CollectedInfo) -> Optional[int]:
        """
        情報を追加（重複時はスキップ）

        Args:
            info: 追加する情報

        Returns:
            追加されたレコードのID（重複時はNone）
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO collected_info (
                        source_type, title, url, content, snippet,
                        published_at, fetched_at, source_name, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        info.source_type,
                        info.title,
                        info.url,
                        info.content,
                        info.snippet,
                        info.published_at.isoformat()
                        if info.published_at
                        else None,
                        info.fetched_at.isoformat(),
                        info.source_name,
                        json.dumps(info.metadata, ensure_ascii=False)
                        if info.metadata
                        else None,
                    ),
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # 重複時はスキップ
                return None

    def get_info_by_id(self, info_id: int) -> Optional[CollectedInfo]:
        """IDで情報を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM collected_info WHERE id = ?", (info_id,)
            )
            row = cursor.fetchone()
            return self._row_to_info(row) if row else None

    def search_info(
        self,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[CollectedInfo]:
        """
        情報を検索

        Args:
            source_type: ソースタイプでフィルタ
            query: タイトル・本文での検索
            start_date: 開始日時
            end_date: 終了日時
            limit: 最大取得件数

        Returns:
            検索結果のリスト
        """
        conditions = []
        params = []

        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)

        if query:
            conditions.append("(title LIKE ? OR content LIKE ? OR snippet LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

        if start_date:
            conditions.append("fetched_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            conditions.append("fetched_at <= ?")
            params.append(end_date.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM collected_info
            WHERE {where_clause}
            ORDER BY fetched_at DESC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_info(row) for row in cursor.fetchall()]

    def delete_old_info(self, days: int = 30) -> int:
        """
        古い情報を削除

        Args:
            days: 保持期間（日数）

        Returns:
            削除件数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM collected_info WHERE fetched_at < ?",
                (cutoff_date.isoformat(),),
            )
            return cursor.rowcount

    def add_summary(self, summary: InfoSummary) -> int:
        """要約を追加"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO info_summaries (
                    summary_type, title, summary_text,
                    source_info_ids, created_at, query
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.summary_type,
                    summary.title,
                    summary.summary_text,
                    json.dumps(summary.source_info_ids),
                    summary.created_at.isoformat(),
                    summary.query,
                ),
            )
            return cursor.lastrowid

    def get_summary_by_id(self, summary_id: int) -> Optional[InfoSummary]:
        """IDで要約を取得"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM info_summaries WHERE id = ?", (summary_id,)
            )
            row = cursor.fetchone()
            return self._row_to_summary(row) if row else None

    def list_summaries(
        self, summary_type: Optional[str] = None, limit: int = 20
    ) -> List[InfoSummary]:
        """要約一覧を取得"""
        if summary_type:
            sql = """
                SELECT * FROM info_summaries
                WHERE summary_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (summary_type, limit)
        else:
            sql = """
                SELECT * FROM info_summaries
                ORDER BY created_at DESC
                LIMIT ?
            """
            params = (limit,)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [self._row_to_summary(row) for row in cursor.fetchall()]

    def _row_to_info(self, row: sqlite3.Row) -> CollectedInfo:
        """DB行をCollectedInfoに変換"""
        return CollectedInfo(
            id=row["id"],
            source_type=row["source_type"],
            title=row["title"],
            url=row["url"],
            content=row["content"],
            snippet=row["snippet"],
            published_at=datetime.fromisoformat(row["published_at"])
            if row["published_at"]
            else None,
            fetched_at=datetime.fromisoformat(row["fetched_at"]),
            source_name=row["source_name"],
            metadata=json.loads(row["metadata_json"])
            if row["metadata_json"]
            else {},
        )

    def _row_to_summary(self, row: sqlite3.Row) -> InfoSummary:
        """DB行をInfoSummaryに変換"""
        return InfoSummary(
            id=row["id"],
            summary_type=row["summary_type"],
            title=row["title"],
            summary_text=row["summary_text"],
            source_info_ids=json.loads(row["source_info_ids"])
            if row["source_info_ids"]
            else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            query=row["query"],
        )
