"""
BashScriptExecutor: subprocess経由での安全なBASHスクリプト実行

設計方針:
- コマンドインジェクション対策（ホワイトリスト方式）
- タイムアウト設定
- エラーハンドリング
- 監査ログ

Design Reference: doc/design/bash_executor.md
Related: P2実装計画（plan/P2_DAILY_LOG_PLAN_v2.md）
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BashResult:
    """BASH実行結果"""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    parsed_json: Optional[Dict[str, Any]] = None


class BashScriptExecutor:
    """安全なBASHスクリプト実行器"""

    # ホワイトリスト: 実行許可するスクリプト
    ALLOWED_SCRIPTS = {
        "journal/init_db.sh",
        "journal/migrate_todos.sh",
        "journal/log_entry.sh",
        "journal/get_entries.sh",
        "journal/search_entries.sh",
        "journal/update_entry.sh",
        "journal/delete_entry.sh",
        "journal/link_todo.sh",
        "journal/generate_summary.sh",
    }

    def __init__(self, scripts_dir: Path = Path("scripts"), timeout: int = 30):
        """
        Args:
            scripts_dir: スクリプトディレクトリ
            timeout: タイムアウト（秒）
        """
        self.scripts_dir = scripts_dir
        self.timeout = timeout

    def execute(
        self, script_name: str, args: Optional[List[str]] = None, parse_json: bool = True
    ) -> BashResult:
        """
        BASHスクリプトを実行

        Args:
            script_name: スクリプト名（相対パス、例: "journal/log_entry.sh"）
            args: スクリプト引数
            parse_json: 標準出力をJSONとしてパースするか

        Returns:
            BashResult: 実行結果

        Raises:
            ValueError: スクリプトがホワイトリストにない場合
            FileNotFoundError: スクリプトファイルが存在しない場合
            subprocess.TimeoutExpired: タイムアウト時
        """
        # ホワイトリストチェック
        if script_name not in self.ALLOWED_SCRIPTS:
            raise ValueError(f"Script not allowed: {script_name}")

        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        # コマンド構築
        cmd = [str(script_path)]
        if args:
            # 引数のサニタイズ（シェル特殊文字のエスケープ）
            cmd.extend(self._sanitize_args(args))

        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,  # exit_codeを自分でチェックする
            )

            success = result.returncode == 0
            parsed_json = None

            if parse_json and success and result.stdout.strip():
                try:
                    parsed_json = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON: {e}")

            return BashResult(
                success=success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                parsed_json=parsed_json,
            )

        except subprocess.TimeoutExpired as e:
            logger.error(f"Script timeout: {script_name}")
            raise

    def _sanitize_args(self, args: List[str]) -> List[str]:
        """
        引数のサニタイズ

        Note:
            subprocess.run()はリスト形式で渡せばシェルインジェクション対策済みだが、
            念のため明示的に危険文字をチェック
        """
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">", "\n", "\r"]

        sanitized = []
        for arg in args:
            if any(char in arg for char in dangerous_chars):
                logger.warning(f"Potentially dangerous argument: {arg}")
                # エスケープまたは拒否
                raise ValueError(f"Argument contains dangerous characters: {arg}")
            sanitized.append(arg)

        return sanitized
