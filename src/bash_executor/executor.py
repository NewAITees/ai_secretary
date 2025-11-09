"""Bashコマンドの安全な実行

このモジュールは、検証済みのBashコマンドを安全に実行し、
作業ディレクトリの追跡と構造化された結果を返します。

Design Reference: doc/design/bash_executor.md
"""

import subprocess
from pathlib import Path
import logging

from .validator import CommandValidator
from .exceptions import ExecutionError, TimeoutError as BashTimeoutError


logger = logging.getLogger(__name__)


class CommandExecutor:
    """Bashコマンドを安全に実行するクラス"""

    def __init__(
        self,
        root_dir: str,
        validator: CommandValidator,
        shell: str = "/bin/bash",
        timeout: int = 30,
    ) -> None:
        """
        初期化

        Args:
            root_dir: ルートディレクトリ
            validator: コマンドバリデーター
            shell: 使用するシェル
            timeout: タイムアウト（秒）
        """
        self.root_dir = Path(root_dir).resolve()
        self.cwd = self.root_dir
        self.validator = validator
        self.shell = shell
        self.timeout = timeout

        # 初期ディレクトリを設定
        if not self.root_dir.exists():
            raise FileNotFoundError(f"ルートディレクトリが存在しません: {self.root_dir}")

        self.cwd = self.root_dir

        logger.info(f"Executor initialized: root={self.root_dir}, cwd={self.cwd}")

    def execute(self, command: str) -> dict[str, str]:
        """
        コマンドを実行

        Args:
            command: 実行するコマンド

        Returns:
            実行結果の辞書（stdout, stderr, cwd, exit_code）

        Raises:
            SecurityError: セキュリティチェックで問題がある場合
            ExecutionError: 実行時エラー
            TimeoutError: タイムアウト
        """
        # バリデーション
        self.validator.validate(command)

        # コマンド実行
        return self._run_command(command)

    def get_cwd(self) -> str:
        """現在の作業ディレクトリを取得

        Returns:
            現在の作業ディレクトリのパス
        """
        return str(self.cwd)

    def _run_command(self, command: str) -> dict[str, str]:
        """
        実際にコマンドを実行

        Args:
            command: 実行するコマンド

        Returns:
            実行結果

        Raises:
            ExecutionError: 実行時エラー
            TimeoutError: タイムアウト
        """
        logger.info(f"Executing command: {command} (cwd: {self.cwd})")

        try:
            # コマンド実行
            result = subprocess.run(
                command,
                shell=True,
                executable=self.shell,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            # cdコマンドの場合、作業ディレクトリを更新
            self._update_cwd_if_needed(command)

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "cwd": str(self.cwd),
                "exit_code": str(result.returncode),
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timeout: {command}")
            raise BashTimeoutError(f"コマンドがタイムアウトしました: {self.timeout}秒")

        except Exception as e:
            logger.error(f"Command execution failed: {command} - {e}")
            raise ExecutionError(f"コマンドの実行に失敗しました: {e}")

    def _update_cwd_if_needed(self, command: str) -> None:
        """
        cdコマンドが含まれる場合、作業ディレクトリを更新

        Args:
            command: 実行したコマンド
        """
        # cdコマンドを含む場合、実際の現在のディレクトリを取得
        if "cd " in command:
            try:
                result = subprocess.run(
                    "pwd",
                    shell=True,
                    executable=self.shell,
                    cwd=str(self.cwd),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    new_cwd = Path(result.stdout.strip())
                    if new_cwd.exists() and new_cwd.is_dir():
                        # ルートディレクトリ外への移動を防止
                        if self._is_within_root(new_cwd):
                            self.cwd = new_cwd
                            logger.info(f"Updated cwd to: {self.cwd}")
                        else:
                            logger.warning(
                                f"Attempted to cd outside root: {new_cwd}, staying at {self.cwd}"
                            )

            except Exception as e:
                logger.warning(f"Failed to update cwd: {e}")

    def _is_within_root(self, path: Path) -> bool:
        """
        パスがルートディレクトリ内かチェック

        Args:
            path: チェックするパス

        Returns:
            ルートディレクトリ内の場合True
        """
        try:
            path.resolve().relative_to(self.root_dir.resolve())
            return True
        except ValueError:
            return False
