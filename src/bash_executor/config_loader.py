"""設定ファイルの読み込みと管理

このモジュールは、YAML形式の設定ファイルとホワイトリストファイルを
読み込み、Bash Executorの設定を管理します。

Design Reference: doc/design/bash_executor.md
"""

import yaml
from pathlib import Path
from typing import Any


class ConfigLoader:
    """設定を読み込み、管理するクラス"""

    def __init__(self, config_path: str = "config/bash_executor/config.yaml") -> None:
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = {}
        self._load_yaml()

    def _load_yaml(self) -> None:
        """YAMLファイルから設定を読み込む

        Raises:
            FileNotFoundError: 設定ファイルが見つからない場合
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得（ドット記法対応）

        Args:
            key: 設定キー（例: "executor.root_dir"）
            default: デフォルト値

        Returns:
            設定値
        """
        keys = key.split(".")
        value: Any = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value

    def load_whitelist(self) -> list[str]:
        """
        ホワイトリストを読み込む

        Returns:
            許可されたコマンドのリスト

        Raises:
            FileNotFoundError: ホワイトリストファイルが見つからない場合
        """
        whitelist_file = self.get("security.whitelist_file")

        if not whitelist_file:
            return []

        path = Path(whitelist_file)
        if not path.exists():
            raise FileNotFoundError(f"ホワイトリストファイルが見つかりません: {path}")

        with open(path, "r", encoding="utf-8") as f:
            # コメントと空行を除外
            commands = [
                line.strip() for line in f if line.strip() and not line.strip().startswith("#")
            ]

        return commands
