"""
Configuration manager for lifelog-system.
"""

import yaml
from pathlib import Path
from typing import Any


class Config:
    """設定管理クラス."""

    def __init__(self, config_path: str = "config/config.yaml") -> None:
        """
        初期化.

        Args:
            config_path: 設定ファイルパス
        """
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """設定ファイルを読み込み."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得.

        Args:
            key: キー（ドット区切りで階層指定可能 例: "collection.sampling_interval"）
            default: デフォルト値

        Returns:
            設定値
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def reload(self) -> None:
        """設定ファイルを再読み込み."""
        self._load()


class PrivacyConfig:
    """プライバシー設定管理クラス."""

    def __init__(self, config_path: str = "config/privacy.yaml") -> None:
        """
        初期化.

        Args:
            config_path: プライバシー設定ファイルパス
        """
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """設定ファイルを読み込み."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Privacy config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    @property
    def store_raw_titles(self) -> bool:
        """タイトル原文を保存するか."""
        return self._config.get("privacy", {}).get("store_raw_titles", False)

    @property
    def store_full_urls(self) -> bool:
        """フルURLを保存するか."""
        return self._config.get("privacy", {}).get("store_full_urls", False)

    @property
    def exclude_processes(self) -> list[str]:
        """除外プロセスリスト."""
        return self._config.get("privacy", {}).get("exclude_processes", [])

    @property
    def sensitive_keywords(self) -> list[str]:
        """センシティブキーワードリスト."""
        return self._config.get("privacy", {}).get("sensitive_keywords", [])
