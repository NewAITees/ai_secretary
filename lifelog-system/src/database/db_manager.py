"""
Database manager for lifelog-system.

Design: Thread-local connections with WAL mode optimization.
See: doc/design/database_design.md
"""

import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

from .schema import CREATE_TABLES_SQL, get_pragma_settings


logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLiteデータベース管理クラス.

    特徴:
    - WALモードで高頻度書き込みに最適化
    - スレッドローカル接続でスレッドセーフ
    - バルク挿入対応
    """

    def __init__(self, db_path: str = "lifelog.db") -> None:
        """
        初期化.

        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()

    def _init_database(self) -> None:
        """データベースの初期化とPRAGMA設定."""
        conn = sqlite3.connect(self.db_path)

        # PRAGMA設定
        for pragma in get_pragma_settings():
            conn.execute(pragma)

        # テーブル作成
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()
        conn.close()

        logger.info(f"Database initialized: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        スレッドローカル接続を取得.

        Returns:
            SQLite接続オブジェクト
        """
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def get_or_create_app(self, process_name: str, process_path_hash: str) -> int:
        """
        アプリケーションマスタからIDを取得（なければ作成）.

        Args:
            process_name: プロセス名
            process_path_hash: プロセスパスのハッシュ

        Returns:
            app_id
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 既存チェック
        cursor.execute(
            """
            SELECT app_id FROM apps
            WHERE process_name = ? AND process_path_hash = ?
        """,
            (process_name, process_path_hash),
        )

        row = cursor.fetchone()
        if row:
            # 最終確認日時を更新
            cursor.execute(
                """
                UPDATE apps SET last_seen = ? WHERE app_id = ?
            """,
                (datetime.now(), row["app_id"]),
            )
            conn.commit()
            return row["app_id"]

        # 新規作成
        cursor.execute(
            """
            INSERT INTO apps (process_name, process_path_hash, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
        """,
            (process_name, process_path_hash, datetime.now(), datetime.now()),
        )
        conn.commit()
        return cursor.lastrowid

    def bulk_insert_intervals(self, intervals: list[dict[str, Any]]) -> None:
        """
        区間データのバルク挿入.

        Args:
            intervals: 区間データのリスト
        """
        if not intervals:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            records = []
            for interval in intervals:
                # app_id を取得または作成
                app_id = self.get_or_create_app(
                    interval["process_name"], interval["process_path_hash"]
                )

                records.append(
                    (
                        interval["start_ts"],
                        interval["end_ts"],
                        app_id,
                        interval["window_hash"],
                        interval.get("domain"),
                        interval["is_idle"],
                    )
                )

            # バルクINSERT
            cursor.executemany(
                """
                INSERT INTO activity_intervals
                (start_ts, end_ts, app_id, window_hash, domain, is_idle)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                records,
            )

            conn.commit()
            logger.debug(f"Bulk inserted {len(records)} intervals")

        except Exception as e:
            conn.rollback()
            logger.error(f"Bulk insert failed: {e}")
            raise

    def save_health_snapshot(self, metrics: dict[str, Any]) -> None:
        """
        ヘルスメトリクスの保存.

        Args:
            metrics: メトリクスデータ
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO health_snapshots
            (ts, cpu_percent, mem_mb, queue_depth,
             collection_delay_p50, collection_delay_p95,
             dropped_events, db_write_time_p95)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                metrics["timestamp"],
                metrics["cpu_percent"],
                metrics["mem_mb"],
                metrics["queue_depth"],
                metrics["collection_delay_p50"],
                metrics["collection_delay_p95"],
                metrics["dropped_events"],
                metrics["db_write_time_p95"],
            ),
        )
        conn.commit()

    def cleanup_old_data(self, retention_days: int = 30) -> None:
        """
        古いデータの削除.

        Args:
            retention_days: 保持日数
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        health_cutoff = datetime.now() - timedelta(days=7)

        cursor.execute(
            """
            DELETE FROM activity_intervals WHERE start_ts < ?
        """,
            (cutoff_date,),
        )

        cursor.execute(
            """
            DELETE FROM health_snapshots WHERE ts < ?
        """,
            (health_cutoff,),
        )

        # 使用されなくなったアプリの削除
        cursor.execute(
            """
            DELETE FROM apps
            WHERE app_id NOT IN (SELECT DISTINCT app_id FROM activity_intervals)
        """
        )

        conn.commit()
        logger.info(f"Cleaned up data older than {retention_days} days")

    def close(self) -> None:
        """データベース接続をクローズ."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            delattr(self._local, "conn")
