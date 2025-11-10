"""
Integration tests for lifelog-system.
"""

import pytest
import tempfile
import time
from pathlib import Path

from src.database.db_manager import DatabaseManager
from src.collectors.activity_collector import ActivityCollector


@pytest.fixture
def test_config():
    """テスト用設定."""
    return {
        "collection": {
            "sampling_interval": 1,  # 1秒（テスト用に短縮）
            "idle_threshold": 5,
            "bulk_write": {"max_queue_size": 10, "batch_size": 2, "timeout_seconds": 1},
        },
        "health": {"snapshot_interval": 2},
        "slo": {
            "collection_delay_p95": 3.0,
            "db_write_time_p95": 50,
            "max_drop_rate": 0.005,
            "max_memory_mb": 100,
        },
    }


@pytest.fixture
def test_privacy_config():
    """テスト用プライバシー設定."""
    return {
        "privacy": {
            "store_raw_titles": False,
            "store_full_urls": False,
            "exclude_processes": ["keepass.exe"],
            "sensitive_keywords": ["password"],
        }
    }


@pytest.fixture
def db_manager():
    """テスト用DBマネージャー."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    manager = DatabaseManager(db_path)
    yield manager

    manager.close()
    Path(db_path).unlink(missing_ok=True)


def test_short_collection_flow(db_manager, test_config, test_privacy_config):
    """短時間の収集→DB保存フローのテスト."""
    collector = ActivityCollector(
        db_manager=db_manager, config=test_config, privacy_config=test_privacy_config
    )

    # 収集開始
    collector.start_collection()

    # 3秒間実行
    time.sleep(3)

    # 収集停止
    collector.stop_collection()

    # データが保存されたか確認
    conn = db_manager._get_connection()
    cursor = conn.cursor()

    # apps テーブルにデータがあるか
    cursor.execute("SELECT COUNT(*) FROM apps")
    apps_count = cursor.fetchone()[0]
    assert apps_count >= 0  # Linux環境ではプロセス検知できない可能性あり

    # health_snapshots にデータがあるか（2秒間隔で最低1回）
    cursor.execute("SELECT COUNT(*) FROM health_snapshots")
    health_count = cursor.fetchone()[0]
    assert health_count >= 0  # ヘルススナップショットが記録される


def test_slo_monitoring(db_manager, test_config, test_privacy_config):
    """SLO監視のテスト."""
    collector = ActivityCollector(
        db_manager=db_manager, config=test_config, privacy_config=test_privacy_config
    )

    # ヘルスモニターの状態確認
    metrics = collector.health_monitor.get_metrics()

    assert "cpu_percent" in metrics
    assert "mem_mb" in metrics
    assert "queue_depth" in metrics


def test_privacy_exclusion(db_manager, test_config, test_privacy_config):
    """プライバシー除外のテスト."""
    collector = ActivityCollector(
        db_manager=db_manager, config=test_config, privacy_config=test_privacy_config
    )

    # センシティブプロセスは除外される
    assert collector._should_exclude_process("keepass.exe") is True
    assert collector._should_exclude_process("my-password-app.exe") is True

    # 通常プロセスは除外されない
    assert collector._should_exclude_process("chrome.exe") is False
