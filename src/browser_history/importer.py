"""Brave browser history importer."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import BrowserHistoryEntry
from .repository import BrowserHistoryRepository


class BraveHistoryImporter:
    """
    Brave履歴インポーター

    BraveブラウザのSQLite履歴データベースから閲覧履歴を読み取り、
    AI SecretaryのDBにインポートします。
    """

    # Chromiumエポック（1601年1月1日）からUnixエポック（1970年1月1日）までの秒数
    UNIX_EPOCH_OFFSET = 11_644_473_600

    def __init__(self, repository: Optional[BrowserHistoryRepository] = None):
        """
        Args:
            repository: BrowserHistoryRepositoryインスタンス
        """
        self.repository = repository or BrowserHistoryRepository()

    @staticmethod
    def chromium_to_datetime(chromium_timestamp: int) -> datetime:
        """
        Chromiumタイムスタンプ（マイクロ秒）をdatetimeに変換

        Args:
            chromium_timestamp: 1601年1月1日からのマイクロ秒

        Returns:
            Pythonのdatetimeオブジェクト
        """
        # マイクロ秒を秒に変換し、Unixエポックからのオフセットを引く
        unix_timestamp = (chromium_timestamp / 1_000_000) - BraveHistoryImporter.UNIX_EPOCH_OFFSET
        return datetime.fromtimestamp(unix_timestamp)

    def find_brave_history_path(self) -> Optional[Path]:
        """
        Brave履歴ファイルを自動検出

        Returns:
            Historyファイルのパス（見つからない場合None）
        """
        # WSL2環境（Windows側）
        wsl_users = Path("/mnt/c/Users")
        if wsl_users.exists():
            for user_dir in wsl_users.iterdir():
                if user_dir.name in ["All Users", "Default", "Default User", "Public"]:
                    continue
                candidate = (
                    user_dir
                    / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History"
                )
                if candidate.exists():
                    return candidate

        # Linux環境
        linux_path = Path.home() / ".config/BraveSoftware/Brave-Browser/Default/History"
        if linux_path.exists():
            return linux_path

        # macOS環境
        mac_path = (
            Path.home()
            / "Library/Application Support/BraveSoftware/Brave-Browser/Default/History"
        )
        if mac_path.exists():
            return mac_path

        return None

    def import_history(
        self,
        brave_history_path: Optional[Path] = None,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """
        Brave履歴をインポート

        Args:
            brave_history_path: Historyファイルのパス（Noneで自動検出）
            limit: インポート件数上限
            since: この日時以降のみインポート

        Returns:
            インポートした件数

        Raises:
            FileNotFoundError: Historyファイルが見つからない場合
            sqlite3.Error: SQLite操作でエラーが発生した場合
        """
        if brave_history_path is None:
            brave_history_path = self.find_brave_history_path()
            if brave_history_path is None:
                raise FileNotFoundError("Brave History file not found")

        # 一時コピー作成（ブラウザ起動中のロック回避）
        temp_copy = Path("/tmp/brave_history_temp.db")
        try:
            shutil.copy(brave_history_path, temp_copy)
        except Exception as e:
            raise IOError(f"Failed to copy History file: {e}") from e

        try:
            entries = self._read_brave_history(temp_copy, limit, since)
            imported_count = 0
            last_visit_time = None

            for entry in entries:
                added_entry = self.repository.add_entry(entry)

                # 重複でない場合のみカウント
                if added_entry is not None:
                    imported_count += 1

                    # 最新の訪問時刻を記録
                    if last_visit_time is None or entry.visit_time > last_visit_time:
                        last_visit_time = entry.visit_time

            # インポートログを記録
            if imported_count > 0:
                self.repository.log_import(
                    str(brave_history_path),
                    imported_count,
                    last_visit_time.isoformat() if last_visit_time else None,
                )

            return imported_count

        finally:
            # 一時ファイル削除
            temp_copy.unlink(missing_ok=True)

    def _read_brave_history(
        self,
        db_path: Path,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> List[BrowserHistoryEntry]:
        """
        Brave履歴データベースから履歴を読み取る

        Args:
            db_path: 履歴データベースのパス
            limit: 取得件数上限
            since: この日時以降のみ取得

        Returns:
            履歴エントリのリスト
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # クエリ構築
        query = """
            SELECT
                v.id as visit_id,
                u.id as url_id,
                u.url,
                u.title,
                v.visit_time,
                v.transition,
                u.visit_count
            FROM visits v
            JOIN urls u ON v.url = u.id
            ORDER BY v.visit_time DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        finally:
            conn.close()

        # データ変換
        entries = []
        for row in rows:
            visit_id, url_id, url, title, visit_time, transition, visit_count = row

            # タイムスタンプ変換
            dt = self.chromium_to_datetime(visit_time)

            # since フィルタ
            if since and dt < since:
                continue

            entry = BrowserHistoryEntry(
                url=url,
                title=title,
                visit_time=dt,
                visit_count=visit_count,
                transition_type=transition,
                brave_url_id=url_id,
                brave_visit_id=visit_id,
            )

            entries.append(entry)

        return entries
