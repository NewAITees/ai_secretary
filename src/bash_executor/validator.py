"""コマンドのセキュリティ検証

このモジュールは、実行するBashコマンドの安全性を検証します。
ホワイトリストベースのコマンド検証と危険なパターンのブロックを行います。

Design Reference: doc/design/bash_executor.md
"""

import re
import shlex
import logging
from typing import Optional, Callable

from .exceptions import CommandNotAllowedError, BlockedPatternError


logger = logging.getLogger(__name__)


class CommandValidator:
    """コマンドの安全性を検証するクラス"""

    def __init__(
        self,
        allowed_commands: list[str],
        block_patterns: list[str],
        approval_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        """
        初期化

        Args:
            allowed_commands: 許可されたコマンドのリスト
            block_patterns: ブロックするパターンのリスト
            approval_callback: ホワイトリスト外コマンドの承認コールバック
                              (command: str, reason: str) -> bool
        """
        self.allowed_commands = set(allowed_commands)
        self.block_patterns = block_patterns
        self.approval_callback = approval_callback

    def validate(self, command: str, reason: str = "") -> None:
        """
        コマンドを検証

        Args:
            command: 検証するコマンド
            reason: コマンドの実行理由（承認リクエスト用）

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
        self._check_whitelist(command, reason)

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

    def _check_whitelist(self, command: str, reason: str = "") -> None:
        """
        ホワイトリストをチェック

        Args:
            command: チェックするコマンド
            reason: コマンドの実行理由（承認リクエスト用）

        Raises:
            CommandNotAllowedError: 許可されていないコマンドの場合
        """
        commands = self._extract_commands(command)

        for cmd in commands:
            if cmd not in self.allowed_commands:
                # 承認コールバックがある場合は承認を試みる
                if self.approval_callback:
                    logger.info(f"ホワイトリスト外コマンド: {cmd} - 承認をリクエストします")
                    approved = self.approval_callback(command, reason)
                    if approved:
                        logger.info(f"コマンド承認されました: {cmd}")
                        continue  # 承認されたので次のコマンドへ
                    else:
                        logger.warning(f"コマンドが拒否されました: {cmd}")
                        raise CommandNotAllowedError(f"コマンドが拒否されました: {cmd}")

                # コールバックがない場合はそのままエラー
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
