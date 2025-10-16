"""
ロギング設定モジュール

設計ドキュメント参照: doc/design/logging.md
"""

import logging
import os
from pathlib import Path


def setup_logger(log_level: str = "INFO", log_file: str = "logs/ai_secretary.log") -> None:
    """
    ロガーのセットアップ

    Args:
        log_level: ログレベル (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: ログファイルのパス
    """
    # ログディレクトリの作成
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # ロガーの設定
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
