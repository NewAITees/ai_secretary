"""Bash Executor Library

安全にBashコマンドを実行するためのライブラリです。
ホワイトリストベースのコマンド検証と危険なパターンのブロックを提供します。

Design Reference: doc/design/bash_executor.md

Example:
    >>> from bash_executor import create_executor
    >>> executor = create_executor()
    >>> result = executor.execute("ls -la")
    >>> print(result['stdout'])
"""

from .exceptions import (
    BashExecutorError,
    SecurityError,
    CommandNotAllowedError,
    BlockedPatternError,
    ExecutionError,
    TimeoutError,
    ConfigurationError,
)
from .config_loader import ConfigLoader
from .validator import CommandValidator
from .executor import CommandExecutor
from .script_executor import BashScriptExecutor, BashResult


__all__ = [
    "BashExecutorError",
    "SecurityError",
    "CommandNotAllowedError",
    "BlockedPatternError",
    "ExecutionError",
    "TimeoutError",
    "ConfigurationError",
    "ConfigLoader",
    "CommandValidator",
    "CommandExecutor",
    "BashScriptExecutor",
    "BashResult",
    "create_executor",
]


def create_executor(config_path: str = "config/bash_executor/config.yaml") -> CommandExecutor:
    """
    デフォルト設定でCommandExecutorを作成するファクトリー関数

    Args:
        config_path: 設定ファイルのパス

    Returns:
        設定済みのCommandExecutorインスタンス

    Raises:
        ConfigurationError: 設定の読み込みに失敗した場合

    Example:
        >>> executor = create_executor()
        >>> result = executor.execute("echo 'Hello, World!'")
        >>> print(result['stdout'])
        Hello, World!
    """
    try:
        # 設定読み込み
        config = ConfigLoader(config_path)

        # ホワイトリスト読み込み
        allowed_commands = config.load_whitelist()

        # ブロックパターン取得
        block_patterns = config.get("security.block_patterns", [])

        # バリデーター作成
        validator = CommandValidator(allowed_commands, block_patterns)

        # Executor作成
        root_dir = config.get("executor.root_dir", ".")
        shell = config.get("executor.shell", "/bin/bash")
        timeout = config.get("executor.timeout", 30)

        executor = CommandExecutor(
            root_dir=root_dir, validator=validator, shell=shell, timeout=timeout
        )

        return executor

    except Exception as e:
        raise ConfigurationError(f"Executorの作成に失敗しました: {e}")
