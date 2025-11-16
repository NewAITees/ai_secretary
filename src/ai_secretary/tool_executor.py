"""
Tool Executor - AI秘書のツール実行レイヤー

設計ドキュメント: plan/P4_P8_P9_design.md (P8セクション)

主要コンポーネント:
- ToolRegistry: ツール定義の読み込みと検証
- CapabilityManager: ロール/権限マッピング管理
- ToolExecutor: 安全なツール実行とレート制限
- ToolAuditLogger: 監査ログ記録
"""

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.bash_executor.bash_script_executor import BashScriptExecutor


class ToolRegistry:
    """ツール定義レジストリ"""

    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._load_tools()

    def _load_tools(self):
        """全ツール定義を読み込み"""
        if not self.tools_dir.exists():
            raise FileNotFoundError(f"Tools directory not found: {self.tools_dir}")

        for yaml_file in self.tools_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                tool_def = yaml.safe_load(f)
                tool_name = tool_def.get("name")
                if tool_name:
                    self.tools[tool_name] = tool_def

    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """ツール定義を取得"""
        return self.tools.get(tool_name)

    def list_tools(self) -> List[str]:
        """登録済みツール一覧を取得"""
        return list(self.tools.keys())


class CapabilityManager:
    """権限管理"""

    def __init__(self, capabilities_file: Path):
        self.capabilities_file = capabilities_file
        self.capabilities: Dict[str, Any] = {}
        self._load_capabilities()

    def _load_capabilities(self):
        """権限マップ読み込み"""
        if not self.capabilities_file.exists():
            raise FileNotFoundError(f"Capabilities file not found: {self.capabilities_file}")

        with open(self.capabilities_file, "r", encoding="utf-8") as f:
            self.capabilities = json.load(f)

    def is_allowed(self, role: str, tool_name: str) -> bool:
        """ツール実行権限チェック"""
        role_config = self.capabilities.get("roles", {}).get(role)
        if not role_config:
            return False

        allowed = role_config.get("allowed_tools", [])
        denied = role_config.get("denied_tools", [])

        # 拒否リスト優先
        for pattern in denied:
            if self._match_pattern(tool_name, pattern):
                return False

        # 許可リスト確認
        for pattern in allowed:
            if self._match_pattern(tool_name, pattern):
                return True

        return False

    def _match_pattern(self, tool_name: str, pattern: str) -> bool:
        """パターンマッチング（*をワイルドカードとして扱う）"""
        if pattern == "*":
            return True
        if "*" in pattern:
            regex = "^" + pattern.replace("*", ".*") + "$"
            return bool(re.match(regex, tool_name))
        return tool_name == pattern


class ToolAuditLogger:
    """ツール監査ログ"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """tool_auditテーブル作成"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    error_message TEXT,
                    elapsed_ms INTEGER,
                    retriable BOOLEAN DEFAULT 0
                );
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_audit_session_id ON tool_audit(session_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_audit_tool_name ON tool_audit(tool_name);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_audit_started_at ON tool_audit(started_at);"
            )

    def log(
        self,
        session_id: str,
        role: str,
        tool_name: str,
        args: Dict[str, Any],
        started_at: datetime,
        finished_at: datetime,
        exit_code: int,
        stdout: str,
        stderr: str,
        error_message: Optional[str],
        retriable: bool,
    ):
        """監査ログ記録"""
        elapsed_ms = int((finished_at - started_at).total_seconds() * 1000)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tool_audit (
                    session_id, role, tool_name, args_json,
                    started_at, finished_at, exit_code,
                    stdout, stderr, error_message, elapsed_ms, retriable
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    role,
                    tool_name,
                    json.dumps(args, ensure_ascii=False),
                    started_at.isoformat(),
                    finished_at.isoformat(),
                    exit_code,
                    stdout,
                    stderr,
                    error_message,
                    elapsed_ms,
                    retriable,
                ),
            )


class RateLimiter:
    """レート制限"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def check_rate_limit(self, tool_name: str, rate_limit: Dict[str, int]) -> bool:
        """レート制限チェック"""
        max_per_hour = rate_limit.get("max_calls_per_hour")
        max_per_day = rate_limit.get("max_calls_per_day")

        with sqlite3.connect(self.db_path) as conn:
            # 1時間以内の呼び出し回数
            if max_per_hour:
                one_hour_ago = datetime.now() - timedelta(hours=1)
                count_hour = conn.execute(
                    "SELECT COUNT(*) FROM tool_audit WHERE tool_name = ? AND started_at > ?",
                    (tool_name, one_hour_ago.isoformat()),
                ).fetchone()[0]

                if count_hour >= max_per_hour:
                    return False

            # 1日以内の呼び出し回数
            if max_per_day:
                one_day_ago = datetime.now() - timedelta(days=1)
                count_day = conn.execute(
                    "SELECT COUNT(*) FROM tool_audit WHERE tool_name = ? AND started_at > ?",
                    (tool_name, one_day_ago.isoformat()),
                ).fetchone()[0]

                if count_day >= max_per_day:
                    return False

        return True


class ToolExecutor:
    """ツール実行器"""

    def __init__(
        self,
        tools_dir: Path,
        capabilities_file: Path,
        audit_db_path: Path,
        project_root: Path,
    ):
        self.registry = ToolRegistry(tools_dir)
        self.capability_manager = CapabilityManager(capabilities_file)
        self.audit_logger = ToolAuditLogger(audit_db_path)
        self.rate_limiter = RateLimiter(audit_db_path)
        self.project_root = project_root

    def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        session_id: str,
        role: str = "assistant",
    ) -> Dict[str, Any]:
        """
        ツール実行

        Args:
            tool_name: ツール名
            args: 引数辞書
            session_id: セッションID
            role: ロール（assistant, system, admin）

        Returns:
            {
                "ok": bool,
                "stdout": str,
                "stderr": str,
                "parsed": Any,  # JSON解析結果
                "metrics": {...}
            }
        """
        started_at = datetime.now()
        exit_code = 0
        stdout = ""
        stderr = ""
        error_message = None
        retriable = False

        try:
            # ツール定義取得
            tool_def = self.registry.get_tool(tool_name)
            if not tool_def:
                raise ValueError(f"Tool not found: {tool_name}")

            # 権限チェック
            if not self.capability_manager.is_allowed(role, tool_name):
                raise PermissionError(f"Role '{role}' is not allowed to use tool '{tool_name}'")

            # レート制限チェック
            rate_limit = tool_def.get("rate_limit", {})
            if rate_limit and not self.rate_limiter.check_rate_limit(tool_name, rate_limit):
                retriable = True
                raise RuntimeError(f"Rate limit exceeded for tool '{tool_name}'")

            # 引数検証
            self._validate_args(tool_def, args)

            # コマンド実行
            command = tool_def["command"]
            timeout = tool_def.get("timeout", 60)

            # BashScriptExecutor を使用
            executor = BashScriptExecutor(project_root=self.project_root)
            result = executor.execute(command, args, timeout=timeout)

            exit_code = result["exit_code"]
            stdout = result["stdout"]
            stderr = result["stderr"]

            if exit_code != 0:
                error_message = stderr or "Command failed"
                retriable = exit_code in [124, 137]  # timeout or killed

            # 出力形式がJSONの場合は解析
            parsed = None
            if tool_def.get("output_format") == "json" and stdout:
                try:
                    parsed = json.loads(stdout)
                except json.JSONDecodeError:
                    pass

            return {
                "ok": exit_code == 0,
                "stdout": stdout,
                "stderr": stderr,
                "parsed": parsed,
                "metrics": {
                    "tool": tool_name,
                    "elapsed_ms": int((datetime.now() - started_at).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat() + "Z",
                },
            }

        except Exception as e:
            error_message = str(e)
            exit_code = -1
            stderr = error_message

            # 引数エラー/権限エラーはリトライ不可
            if isinstance(e, (ValueError, PermissionError)):
                retriable = False
            else:
                retriable = True

            return {
                "ok": False,
                "stdout": stdout,
                "stderr": stderr,
                "error": error_message,
                "metrics": {
                    "tool": tool_name,
                    "elapsed_ms": int((datetime.now() - started_at).total_seconds() * 1000),
                    "timestamp": datetime.now().isoformat() + "Z",
                },
            }

        finally:
            # 監査ログ記録
            finished_at = datetime.now()
            self.audit_logger.log(
                session_id=session_id,
                role=role,
                tool_name=tool_name,
                args=args,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                error_message=error_message,
                retriable=retriable,
            )

    def _validate_args(self, tool_def: Dict[str, Any], args: Dict[str, Any]):
        """引数スキーマ検証"""
        args_schema = tool_def.get("args_schema", {})

        for arg_name, schema in args_schema.items():
            # 必須チェック
            if schema.get("required", False) and arg_name not in args:
                raise ValueError(f"Required argument missing: {arg_name}")

            # 型チェック
            if arg_name in args:
                value = args[arg_name]
                arg_type = schema.get("type")

                if arg_type == "string" and not isinstance(value, str):
                    raise ValueError(f"Argument '{arg_name}' must be a string")
                elif arg_type == "int" and not isinstance(value, int):
                    raise ValueError(f"Argument '{arg_name}' must be an integer")
                elif arg_type == "boolean" and not isinstance(value, bool):
                    raise ValueError(f"Argument '{arg_name}' must be a boolean")

                # 列挙値チェック
                if "enum" in schema and value not in schema["enum"]:
                    raise ValueError(
                        f"Argument '{arg_name}' must be one of {schema['enum']}, got '{value}'"
                    )

                # パターンチェック（文字列のみ）
                if arg_type == "string" and "pattern" in schema:
                    pattern = schema["pattern"]
                    if not re.match(pattern, value):
                        raise ValueError(
                            f"Argument '{arg_name}' does not match pattern: {pattern}"
                        )

        # デフォルト値適用
        for arg_name, schema in args_schema.items():
            if arg_name not in args and "default" in schema:
                args[arg_name] = schema["default"]
