"""
Collectors tests for lifelog-system.
"""

import pytest
from src.utils.privacy import stable_hash, extract_domain_if_browser, is_sensitive_process
from src.collectors.health_monitor import HealthMonitor


class TestPrivacyFunctions:
    """プライバシー関数のテスト."""

    def test_stable_hash(self):
        """ハッシュの安定性テスト."""
        text = "test window title"

        h1 = stable_hash(text)
        h2 = stable_hash(text)

        # 同じ入力は同じハッシュ
        assert h1 == h2

        # ハッシュ長は16文字
        assert len(h1) == 16

        # 異なる入力は異なるハッシュ
        h3 = stable_hash("different text")
        assert h1 != h3

    def test_extract_domain_if_browser(self):
        """ブラウザのドメイン抽出テスト."""
        # ブラウザの場合（ドメイン含む）
        title = "example.com - Google Chrome"
        domain = extract_domain_if_browser(title, "chrome.exe")
        assert domain == "example.com"

        # ブラウザ以外の場合
        domain = extract_domain_if_browser("Notepad", "notepad.exe")
        assert domain is None

    def test_is_sensitive_process(self):
        """センシティブプロセス判定テスト."""
        sensitive_keywords = ["password", "credential", "secret"]

        # センシティブな場合
        assert is_sensitive_process("keepass.exe", sensitive_keywords) is False
        assert is_sensitive_process("my-password-manager.exe", sensitive_keywords) is True

        # センシティブでない場合
        assert is_sensitive_process("chrome.exe", sensitive_keywords) is False


class TestHealthMonitor:
    """ヘルスモニターのテスト."""

    def test_record_collection_delay(self):
        """収集遅延の記録テスト."""
        monitor = HealthMonitor()

        monitor.record_collection_delay(0.5)
        monitor.record_collection_delay(1.0)
        monitor.record_collection_delay(1.5)

        metrics = monitor.get_metrics()

        assert metrics["queue_depth"] == 3
        assert metrics["collection_delay_p50"] > 0
        assert metrics["collection_delay_p95"] > 0

    def test_record_write_time(self):
        """書込時間の記録テスト."""
        monitor = HealthMonitor()

        # collection_delayも記録しないとget_metrics()がスキップする
        monitor.record_collection_delay(0.1)
        monitor.record_write_time(10.0)
        monitor.record_write_time(20.0)
        monitor.record_write_time(30.0)

        metrics = monitor.get_metrics()

        assert metrics["db_write_time_p95"] > 0

    def test_record_drop(self):
        """ドロップイベントの記録テスト."""
        monitor = HealthMonitor()

        monitor.record_drop()
        monitor.record_drop()

        metrics = monitor.get_metrics()

        assert metrics["dropped_events"] == 2

    def test_check_slo(self):
        """SLOチェックのテスト."""
        monitor = HealthMonitor()

        # 正常範囲のデータ
        monitor.record_collection_delay(0.5)
        monitor.record_write_time(10.0)

        config = {
            "collection_delay_p95": 3.0,
            "db_write_time_p95": 50,
            "max_memory_mb": 100,
        }

        result = monitor.check_slo(config)

        assert result["healthy"] is True
        assert len(result["violations"]) == 0

    def test_check_slo_violations(self):
        """SLO違反検知のテスト."""
        monitor = HealthMonitor()

        # 違反データ
        monitor.record_collection_delay(5.0)  # > 3.0秒
        monitor.record_drop()

        config = {
            "collection_delay_p95": 3.0,
            "db_write_time_p95": 50,
            "max_memory_mb": 100,
        }

        result = monitor.check_slo(config)

        assert result["healthy"] is False
        assert len(result["violations"]) > 0
