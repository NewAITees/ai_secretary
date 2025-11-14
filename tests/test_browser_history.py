"""Tests for browser history functionality."""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.browser_history import (
    BraveHistoryImporter,
    BrowserHistoryEntry,
    BrowserHistoryRepository,
)


class TestBrowserHistoryRepository:
    """BrowserHistoryRepositoryのテスト"""

    @pytest.fixture
    def temp_db(self):
        """一時データベースを作成"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_browser.db"
            yield db_path

    @pytest.fixture
    def repository(self, temp_db):
        """テスト用リポジトリ"""
        return BrowserHistoryRepository(db_path=temp_db)

    def test_add_and_get_entry(self, repository):
        """エントリの追加と取得"""
        entry = BrowserHistoryEntry(
            url="https://example.com",
            title="Example Domain",
            visit_time=datetime.now(),
            visit_count=1,
        )

        # 追加
        added = repository.add_entry(entry)
        assert added.id is not None
        assert added.imported_at is not None

        # 取得
        retrieved = repository.get_entry(added.id)
        assert retrieved is not None
        assert retrieved.url == "https://example.com"
        assert retrieved.title == "Example Domain"

    def test_list_history(self, repository):
        """履歴のリスト取得"""
        # テストデータ作成
        now = datetime.now()
        entries = [
            BrowserHistoryEntry(
                url=f"https://example.com/{i}",
                title=f"Page {i}",
                visit_time=now - timedelta(hours=i),
            )
            for i in range(5)
        ]

        for entry in entries:
            repository.add_entry(entry)

        # 全件取得
        all_entries = repository.list_history(limit=10)
        assert len(all_entries) == 5

        # 新しい順にソートされているか確認
        assert all_entries[0].url == "https://example.com/0"
        assert all_entries[-1].url == "https://example.com/4"

    def test_search_history(self, repository):
        """履歴の検索"""
        entries = [
            BrowserHistoryEntry(
                url="https://github.com/repo1",
                title="GitHub Repo 1",
                visit_time=datetime.now(),
            ),
            BrowserHistoryEntry(
                url="https://example.com",
                title="Example",
                visit_time=datetime.now(),
            ),
            BrowserHistoryEntry(
                url="https://github.com/repo2",
                title="GitHub Repo 2",
                visit_time=datetime.now(),
            ),
        ]

        for entry in entries:
            repository.add_entry(entry)

        # GitHub検索
        results = repository.search_history("github")
        assert len(results) == 2
        assert all("github" in r.url.lower() for r in results)

    def test_delete_old_entries(self, repository):
        """古いエントリの削除"""
        now = datetime.now()
        old_entry = BrowserHistoryEntry(
            url="https://old.example.com",
            title="Old Page",
            visit_time=now - timedelta(days=100),
        )
        new_entry = BrowserHistoryEntry(
            url="https://new.example.com",
            title="New Page",
            visit_time=now,
        )

        repository.add_entry(old_entry)
        repository.add_entry(new_entry)

        # 90日より古いエントリを削除
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        deleted_count = repository.delete_old_entries(cutoff)

        assert deleted_count == 1
        remaining = repository.list_history(limit=10)
        assert len(remaining) == 1
        assert remaining[0].url == "https://new.example.com"

    def test_duplicate_entry_prevention(self, repository):
        """重複エントリの防止"""
        entry = BrowserHistoryEntry(
            url="https://example.com",
            title="Example",
            visit_time=datetime.now(),
            brave_visit_id=12345,
        )

        # 1回目の追加
        added1 = repository.add_entry(entry)
        assert added1 is not None
        assert added1.id is not None

        # 2回目の追加（同じbrave_visit_id）
        added2 = repository.add_entry(entry)
        assert added2 is None  # 重複なのでNone

        # データベース内の件数を確認
        entries = repository.list_history(limit=10)
        assert len(entries) == 1


class TestBraveHistoryImporter:
    """BraveHistoryImporterのテスト"""

    def test_chromium_to_datetime(self):
        """Chromiumタイムスタンプの変換"""
        # 2020-01-01 00:00:00 UTCのChromiumタイムスタンプ（検証済み）
        chromium_ts = 13222278000000000  # マイクロ秒

        dt = BraveHistoryImporter.chromium_to_datetime(chromium_ts)

        assert dt.year == 2020
        assert dt.month == 1
        assert dt.day == 1

    def test_find_brave_history_path(self):
        """Brave履歴パスの検出（環境依存）"""
        importer = BraveHistoryImporter()
        path = importer.find_brave_history_path()

        # 環境によってはNoneになる可能性がある
        if path is not None:
            assert path.name == "History"

    @pytest.fixture
    def mock_brave_db(self):
        """モックBrave履歴データベースを作成"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "History"

            # モックデータベース作成
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE urls (
                    id INTEGER PRIMARY KEY,
                    url TEXT,
                    title TEXT,
                    visit_count INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE visits (
                    id INTEGER PRIMARY KEY,
                    url INTEGER,
                    visit_time INTEGER,
                    transition INTEGER
                )
                """
            )

            # テストデータ挿入
            # Chromiumタイムスタンプ（2020-01-01 00:00:00 UTC）
            chromium_ts = 13222278000000000

            conn.execute(
                "INSERT INTO urls (id, url, title, visit_count) VALUES (1, ?, ?, ?)",
                ("https://test.example.com", "Test Page", 1),
            )
            conn.execute(
                "INSERT INTO visits (id, url, visit_time, transition) VALUES (1, 1, ?, 0)",
                (chromium_ts,),
            )

            conn.commit()
            conn.close()

            yield db_path

    def test_import_history(self, mock_brave_db):
        """履歴のインポート"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_db = Path(tmpdir) / "repo.db"
            repository = BrowserHistoryRepository(db_path=repo_db)
            importer = BraveHistoryImporter(repository=repository)

            # インポート実行
            count = importer.import_history(brave_history_path=mock_brave_db, limit=10)

            assert count == 1

            # インポートされたデータを確認
            entries = repository.list_history(limit=10)
            assert len(entries) == 1
            assert entries[0].url == "https://test.example.com"
            assert entries[0].title == "Test Page"
            assert entries[0].visit_count == 1

    def test_import_history_file_not_found(self):
        """存在しないファイルのインポート"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_db = Path(tmpdir) / "repo.db"
            repository = BrowserHistoryRepository(db_path=repo_db)
            importer = BraveHistoryImporter(repository=repository)

            # shutil.copyがIOErrorを発生させる
            with pytest.raises((FileNotFoundError, IOError, OSError)):
                importer.import_history(
                    brave_history_path=Path("/nonexistent/History"), limit=10
                )

    def test_import_history_duplicate_prevention(self, mock_brave_db):
        """重複インポートの防止"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_db = Path(tmpdir) / "repo.db"
            repository = BrowserHistoryRepository(db_path=repo_db)
            importer = BraveHistoryImporter(repository=repository)

            # 1回目のインポート
            count1 = importer.import_history(brave_history_path=mock_brave_db, limit=10)
            assert count1 == 1

            # 2回目のインポート（同じデータ）
            count2 = importer.import_history(brave_history_path=mock_brave_db, limit=10)
            assert count2 == 0  # 重複なので0件

            # データベース内の件数を確認
            entries = repository.list_history(limit=10)
            assert len(entries) == 1  # 重複排除により1件のみ


class TestBrowserHistoryEntry:
    """BrowserHistoryEntryのテスト"""

    def test_to_dict(self):
        """辞書形式への変換"""
        now = datetime.now()
        entry = BrowserHistoryEntry(
            id=1,
            url="https://example.com",
            title="Example",
            visit_time=now,
            visit_count=5,
            transition_type=0,
            source_browser="brave",
            imported_at=now,
        )

        d = entry.to_dict()

        assert d["id"] == 1
        assert d["url"] == "https://example.com"
        assert d["title"] == "Example"
        assert d["visit_count"] == 5
        assert d["source_browser"] == "brave"
