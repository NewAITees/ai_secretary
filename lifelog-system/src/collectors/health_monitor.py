"""
Health monitoring for lifelog-system.

SLO観測可能性の実装
"""

import psutil
import logging
from collections import deque
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    ヘルスモニタリングクラス.

    SLO指標を収集・監視する。
    """

    def __init__(self) -> None:
        """初期化."""
        self.collection_delays = deque(maxlen=1000)
        self.write_times = deque(maxlen=1000)
        self.dropped_count = 0

    def record_collection_delay(self, delay_seconds: float) -> None:
        """
        イベント発生→DB書込の遅延を記録.

        Args:
            delay_seconds: 遅延秒数
        """
        self.collection_delays.append(delay_seconds)

    def record_write_time(self, time_ms: float) -> None:
        """
        DB書込時間を記録.

        Args:
            time_ms: 書込時間（ミリ秒）
        """
        self.write_times.append(time_ms)

    def record_drop(self) -> None:
        """ドロップイベントをカウント."""
        self.dropped_count += 1

    def get_metrics(self) -> dict[str, Any]:
        """
        現在のメトリクスを取得.

        Returns:
            メトリクスデータ
        """
        if not self.collection_delays:
            return {
                "timestamp": datetime.now(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "mem_mb": psutil.Process().memory_info().rss / 1024 / 1024,
                "queue_depth": 0,
                "collection_delay_p50": 0.0,
                "collection_delay_p95": 0.0,
                "dropped_events": self.dropped_count,
                "db_write_time_p95": 0.0,
            }

        delays_sorted = sorted(self.collection_delays)
        writes_sorted = sorted(self.write_times) if self.write_times else [0.0]

        return {
            "timestamp": datetime.now(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "mem_mb": psutil.Process().memory_info().rss / 1024 / 1024,
            "queue_depth": len(self.collection_delays),
            "collection_delay_p50": delays_sorted[len(delays_sorted) // 2],
            "collection_delay_p95": delays_sorted[int(len(delays_sorted) * 0.95)],
            "dropped_events": self.dropped_count,
            "db_write_time_p95": writes_sorted[int(len(writes_sorted) * 0.95)],
        }

    def check_slo(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        SLO違反をチェック.

        Args:
            config: SLO設定

        Returns:
            チェック結果
        """
        metrics = self.get_metrics()
        violations = []

        # 遅延チェック
        if metrics.get("collection_delay_p95", 0) > config.get("collection_delay_p95", 3.0):
            violations.append(
                f"Collection delay P95 > {config.get('collection_delay_p95')}s"
            )

        # ドロップ率チェック
        if self.dropped_count > 0:
            violations.append(f"Dropped events: {self.dropped_count}")

        # 書込時間チェック
        if metrics.get("db_write_time_p95", 0) > config.get("db_write_time_p95", 50):
            violations.append(f"DB write time P95 > {config.get('db_write_time_p95')}ms")

        # メモリチェック
        if metrics.get("mem_mb", 0) > config.get("max_memory_mb", 100):
            violations.append(f"Memory usage > {config.get('max_memory_mb')}MB")

        return {"healthy": len(violations) == 0, "violations": violations, "metrics": metrics}
