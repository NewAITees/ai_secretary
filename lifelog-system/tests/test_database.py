"""
Database tests for lifelog-system.
"""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from src.database.db_manager import DatabaseManager


@pytest.fixture
def db_manager():
    """テスト用のインメモリDBマネージャーを作成."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    manager = DatabaseManager(db_path)
    yield manager

    # クリーンアップ
    manager.close()
    Path(db_path).unlink(missing_ok=True)


def test_database_initialization(db_manager):
    """データベース初期化のテスト."""
    conn = db_manager._get_connection()
    cursor = conn.cursor()

    # テーブルが存在するか確認
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "apps" in tables
    assert "activity_intervals" in tables
    assert "health_snapshots" in tables


def test_get_or_create_app(db_manager):
    """アプリマスタのCRUDテスト."""
    # 新規作成
    app_id1 = db_manager.get_or_create_app("chrome.exe", "hash123")
    assert app_id1 > 0

    # 同じアプリは同じIDが返る
    app_id2 = db_manager.get_or_create_app("chrome.exe", "hash123")
    assert app_id1 == app_id2

    # 異なるアプリは異なるIDが返る
    app_id3 = db_manager.get_or_create_app("firefox.exe", "hash456")
    assert app_id3 != app_id1


def test_bulk_insert_intervals(db_manager):
    """バルク挿入のテスト."""
    now = datetime.now()

    intervals = [
        {
            "start_ts": now,
            "end_ts": now,
            "process_name": "test.exe",
            "process_path_hash": "hash_test",
            "window_hash": "title_hash_1",
            "domain": None,
            "is_idle": 0,
        },
        {
            "start_ts": now,
            "end_ts": now,
            "process_name": "test2.exe",
            "process_path_hash": "hash_test2",
            "window_hash": "title_hash_2",
            "domain": "example.com",
            "is_idle": 1,
        },
    ]

    db_manager.bulk_insert_intervals(intervals)

    # 挿入確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activity_intervals")
    count = cursor.fetchone()[0]

    assert count == 2

    # データ内容確認
    cursor.execute("SELECT window_hash, domain, is_idle FROM activity_intervals")
    rows = cursor.fetchall()

    assert rows[0][0] == "title_hash_1"
    assert rows[0][1] is None
    assert rows[0][2] == 0

    assert rows[1][0] == "title_hash_2"
    assert rows[1][1] == "example.com"
    assert rows[1][2] == 1


def test_save_health_snapshot(db_manager):
    """ヘルススナップショット保存のテスト."""
    metrics = {
        "timestamp": datetime.now(),
        "cpu_percent": 15.5,
        "mem_mb": 50.2,
        "queue_depth": 10,
        "collection_delay_p50": 0.5,
        "collection_delay_p95": 1.2,
        "dropped_events": 0,
        "db_write_time_p95": 25.0,
    }

    db_manager.save_health_snapshot(metrics)

    # 保存確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM health_snapshots")
    count = cursor.fetchone()[0]

    assert count == 1

    # データ内容確認
    cursor.execute("SELECT cpu_percent, mem_mb, queue_depth FROM health_snapshots")
    row = cursor.fetchone()

    assert row[0] == 15.5
    assert row[1] == 50.2
    assert row[2] == 10


def test_cleanup_old_data(db_manager):
    """古いデータ削除のテスト."""
    # テストデータ挿入
    from datetime import timedelta

    old_time = datetime.now() - timedelta(days=40)
    recent_time = datetime.now()

    intervals = [
        {
            "start_ts": old_time,
            "end_ts": old_time,
            "process_name": "old.exe",
            "process_path_hash": "hash_old",
            "window_hash": "title_old",
            "domain": None,
            "is_idle": 0,
        },
        {
            "start_ts": recent_time,
            "end_ts": recent_time,
            "process_name": "recent.exe",
            "process_path_hash": "hash_recent",
            "window_hash": "title_recent",
            "domain": None,
            "is_idle": 0,
        },
    ]

    db_manager.bulk_insert_intervals(intervals)

    # クリーンアップ実行（30日保持）
    db_manager.cleanup_old_data(retention_days=30)

    # 確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activity_intervals")
    count = cursor.fetchone()[0]

    # 古いデータは削除され、最近のデータのみ残る
    assert count == 1
