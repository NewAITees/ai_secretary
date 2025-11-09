"""Bash Executor Library - エージェント統合例

このスクリプトは、Bash Executor LibraryをAIエージェントと統合する例を示します。
実際のLLM連携は含まれていませんが、エージェント側での実装イメージを提供します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.bash_executor import create_executor, SecurityError, ExecutionError


class SimpleAgent:
    """シンプルなエージェントの例（LLM連携なし）"""

    def __init__(self) -> None:
        self.executor = create_executor()
        self.history: list[dict[str, str | bool | dict[str, str]]] = []

    def execute_command(self, command: str, auto_confirm: bool = False) -> dict[str, str]:
        """
        コマンドを実行（確認機能付き）

        Args:
            command: 実行するコマンド
            auto_confirm: 自動承認するか

        Returns:
            実行結果
        """
        print(f"\n実行するコマンド: {command}")

        # 確認
        if not auto_confirm:
            confirm = input("実行しますか？ [y/N]: ").strip().lower()
            if confirm != "y":
                return {"error": "ユーザーによってキャンセルされました"}

        # 実行
        try:
            result = self.executor.execute(command)
            self.history.append({"command": command, "result": result, "success": True})
            return result
        except (SecurityError, ExecutionError) as e:
            error_result = {"error": str(e)}
            self.history.append({"command": command, "result": error_result, "success": False})
            return error_result

    def show_history(self) -> None:
        """実行履歴を表示"""
        print("\n=== 実行履歴 ===")
        for i, entry in enumerate(self.history, 1):
            print(f"{i}. {entry['command']}")
            print(f"   成功: {entry['success']}")


def main() -> None:
    """エージェント統合例"""

    print("=== Bash Executor - エージェント統合例 ===")
    print("簡単なコマンド実行エージェントのデモです\n")

    agent = SimpleAgent()

    # いくつかのコマンドを実行
    commands = [
        "pwd",
        "ls -la",
        "echo 'Hello from agent!'",
        "echo 'Current date:' && date",
    ]

    for cmd in commands:
        result = agent.execute_command(cmd, auto_confirm=True)

        if "error" in result:
            print(f"❌ エラー: {result['error']}")
        else:
            print(f"✅ 成功")
            if result.get("stdout"):
                stdout = result["stdout"]
                # 長い出力は切り詰める
                if len(stdout) > 100:
                    print(f"出力: {stdout[:100]}...")
                else:
                    print(f"出力: {stdout.strip()}")

    # 履歴表示
    agent.show_history()

    # インタラクティブモード
    print("\n=== インタラクティブモード ===")
    print("コマンドを入力してください（'quit'で終了）")

    while True:
        try:
            command = input("\n> ").strip()
            if command.lower() in ["quit", "exit", "q"]:
                break

            if not command:
                continue

            result = agent.execute_command(command, auto_confirm=False)

            if "error" in result:
                print(f"❌ エラー: {result['error']}")
            else:
                print(f"✅ 成功")
                print(f"出力:\n{result.get('stdout', '')}")
                if result.get("stderr"):
                    print(f"エラー出力:\n{result['stderr']}")

        except KeyboardInterrupt:
            print("\n\n終了します")
            break

    # 最終履歴表示
    agent.show_history()


if __name__ == "__main__":
    main()
