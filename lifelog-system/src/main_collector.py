#!/usr/bin/env python3
"""
Main collector script for lifelog-system.

Usage:
    python src/main_collector.py [--config CONFIG_PATH] [--duration SECONDS]
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from src.database.db_manager import DatabaseManager
from src.collectors.activity_collector import ActivityCollector
from src.utils.config import Config, PrivacyConfig


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def setup_signal_handlers(collector: ActivityCollector) -> None:
    """シグナルハンドラーを設定."""

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, stopping collection...")
        collector.stop_collection()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main() -> None:
    """メインエントリーポイント."""
    parser = argparse.ArgumentParser(description="Lifelog Activity Collector")
    parser.add_argument(
        "--config", type=str, default="config/config.yaml", help="Config file path"
    )
    parser.add_argument(
        "--privacy-config",
        type=str,
        default="config/privacy.yaml",
        help="Privacy config file path",
    )
    parser.add_argument(
        "--duration", type=int, default=None, help="Run duration in seconds (default: infinite)"
    )
    args = parser.parse_args()

    # 設定読み込み
    try:
        config = Config(args.config)
        privacy_config = PrivacyConfig(args.privacy_config)
    except FileNotFoundError as e:
        logger.error(f"Config file not found: {e}")
        sys.exit(1)

    # データベース初期化
    db_path = config.get("database.path", "lifelog.db")
    db_manager = DatabaseManager(db_path)

    # コレクター初期化
    collector = ActivityCollector(
        db_manager=db_manager,
        config=config._config,
        privacy_config=privacy_config._config,
    )

    # シグナルハンドラー設定
    setup_signal_handlers(collector)

    # 収集開始
    logger.info("Starting activity collection...")
    collector.start_collection()

    # 実行時間制限がある場合
    if args.duration:
        logger.info(f"Running for {args.duration} seconds...")
        time.sleep(args.duration)
        collector.stop_collection()
        logger.info("Collection completed")
    else:
        # 無限ループ
        logger.info("Running indefinitely (Ctrl+C to stop)...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            collector.stop_collection()
            logger.info("Collection stopped by user")


if __name__ == "__main__":
    main()
