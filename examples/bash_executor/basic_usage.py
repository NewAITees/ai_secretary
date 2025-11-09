"""Bash Executor Library - 基本的な使用例

このスクリプトは、Bash Executor Libraryの基本的な使い方を示します。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.bash_executor import create_executor, SecurityError, ExecutionError


def main() -> None:
    """基本的な使用例"""

    print("=== Bash Executor Library - 基本的な使用例 ===\n")

    # Executorを作成
    executor = create_executor()

    # 例1: シンプルなコマンド
    print("例1: ディレクトリの内容を表示")
    try:
        result = executor.execute("ls -la")
        print(f"出力:\n{result['stdout'][:200]}...")  # 最初の200文字のみ表示
        print(f"作業ディレクトリ: {result['cwd']}\n")
    except Exception as e:
        print(f"エラー: {e}\n")

    # 例2: pwdコマンド
    print("例2: 現在のディレクトリを表示")
    try:
        result = executor.execute("pwd")
        print(f"出力: {result['stdout'].strip()}")
        print(f"現在の作業ディレクトリ: {executor.get_cwd()}\n")
    except Exception as e:
        print(f"エラー: {e}\n")

    # 例3: セキュリティエラー（ブロックされたパターン）
    print("例3: セキュリティエラー（ブロックされたパターン）")
    try:
        result = executor.execute("echo `whoami`")
        print(f"出力: {result['stdout']}\n")
    except SecurityError as e:
        print(f"✓ 予想通りセキュリティエラー: {e}\n")

    # 例4: セキュリティエラー（許可されていないコマンド）
    print("例4: セキュリティエラー（許可されていないコマンド）")
    try:
        result = executor.execute("sudo apt update")
        print(f"出力: {result['stdout']}\n")
    except SecurityError as e:
        print(f"✓ 予想通りセキュリティエラー: {e}\n")

    # 例5: パイプとリダイレクト
    print("例5: パイプの使用")
    try:
        result = executor.execute("ls -1 | head -5")
        print(f"出力:\n{result['stdout']}\n")
    except Exception as e:
        print(f"エラー: {e}\n")

    # 例6: 複数コマンドの実行
    print("例6: 複数コマンドの実行（&&）")
    try:
        result = executor.execute("echo 'Hello' && echo 'World'")
        print(f"出力:\n{result['stdout']}\n")
    except Exception as e:
        print(f"エラー: {e}\n")

    # 例7: エラーハンドリング
    print("例7: 存在しないファイルの処理")
    try:
        result = executor.execute("cat /nonexistent_file_12345")
        print(f"標準出力: {result['stdout']}")
        print(f"標準エラー: {result['stderr']}")
        print(f"終了コード: {result['exit_code']}\n")
    except Exception as e:
        print(f"エラー: {e}\n")


if __name__ == "__main__":
    main()
