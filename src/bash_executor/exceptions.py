"""Bash Executorのカスタム例外定義

このモジュールは、Bash Executor Libraryで使用される
カスタム例外クラスを定義します。

Design Reference: doc/design/bash_executor.md
"""


class BashExecutorError(Exception):
    """Bash Executor基底例外"""

    pass


class SecurityError(BashExecutorError):
    """セキュリティ関連のエラー"""

    pass


class CommandNotAllowedError(SecurityError):
    """許可されていないコマンド"""

    pass


class BlockedPatternError(SecurityError):
    """ブロックされたパターンを含む"""

    pass


class ExecutionError(BashExecutorError):
    """コマンド実行エラー"""

    pass


class TimeoutError(ExecutionError):
    """タイムアウトエラー"""

    pass


class ConfigurationError(BashExecutorError):
    """設定エラー"""

    pass
