"""コマンドのセキュリティ検証

このモジュールは、実行するBashコマンドの安全性を検証します。
ホワイトリストベースのコマンド検証と危険なパターンのブロックを行います。

Design Reference: doc/design/bash_executor.md
"""

import re
import shlex
import logging

from .exceptions import CommandNotAllowedError, BlockedPatternError


logger = logging.getLogger(__name__)


class CommandValidator:
    """コマンドの安全性を検証するクラス"""

    def __init__(self, allowed_commands: list[str], block_patterns: list[str]) -> None:
        """
        初期化

        Args:
            allowed_commands: 許可されたコマンドのリスト
            block_patterns: ブロックするパターンのリスト
        """
        self.allowed_commands = set(allowed_commands)
        self.block_patterns = block_patterns

    def validate(self, command: str) -> None:
        """
        コマンドを検証

        Args:
            command: 検証するコマンド

        Raises:
            ValueError: コマンドが空の場合
            BlockedPatternError: ブロックされたパターンが含まれる場合
            CommandNotAllowedError: 許可されていないコマンドの場合
        """
        if not command or not command.strip():
            raise ValueError("コマンドが空です")

        # ブロックパターンのチェック
        self._check_blocked_patterns(command)

        # ホワイトリストチェック
        self._check_whitelist(command)

    def _check_blocked_patterns(self, command: str) -> None:
        """
        ブロックパターンをチェック

        Args:
            command: チェックするコマンド

        Raises:
            BlockedPatternError: ブロックされたパターンが含まれる場合
        """
        for pattern in self.block_patterns:
            if pattern in command:
                logger.warning(f"ブロックされたパターン検出: {pattern}")
                raise BlockedPatternError(f"禁止されたパターンが含まれています: {pattern}")

    def _check_whitelist(self, command: str) -> None:
        """
        ホワイトリストをチェック

        Args:
            command: チェックするコマンド

        Raises:
            CommandNotAllowedError: 許可されていないコマンドの場合
        """
        commands = self._extract_commands(command)

        for cmd in commands:
            if cmd not in self.allowed_commands:
                logger.warning(f"許可されていないコマンド: {cmd}")
                raise CommandNotAllowedError(f"許可されていないコマンドです: {cmd}")

    def _extract_commands(self, command_str: str) -> list[str]:
        """
        コマンド文字列からコマンド名を抽出

        Args:
            command_str: コマンド文字列

        Returns:
            コマンド名のリスト

        Raises:
            CommandNotAllowedError: パースエラーの場合
        """
        # パイプ、セミコロン、&&、||で分割
        parts = re.split(r"[|;&]+|\s*&&\s*|\s*\|\|\s*", command_str)
        commands = []

        for part in parts:
            part = part.strip()
            if not part:
                continue

            try:
                # 最初のトークンがコマンド名
                tokens = shlex.split(part)
                if tokens:
                    commands.append(tokens[0])
            except ValueError as e:
                # パースエラーの場合は安全のためブロック
                logger.warning(f"コマンドのパースに失敗: {part} - {e}")
                raise CommandNotAllowedError(f"コマンドのパースに失敗しました: {part}")

        return commands
