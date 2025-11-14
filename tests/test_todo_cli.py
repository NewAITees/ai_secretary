"""TODO CLI の動作テスト"""

import json
import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    """CLI実行ヘルパー"""
    cmd = [
        sys.executable,
        "-m",
        "src.todo.cli",
        "--db-path",
        str(db_path),
    ] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )


def test_cli_list_empty(tmp_path):
    """空のリスト取得"""
    db_path = tmp_path / "cli_test.db"
    result = run_cli(["list", "--format", "json"], db_path)
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_cli_add_and_list(tmp_path):
    """TODO追加とリスト取得"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    result = run_cli(
        [
            "add",
            "--title",
            "会議準備",
            "--description",
            "資料作成とリハーサル",
            "--due-date",
            "2025-12-15",
            "--status",
            "doing",
            "--format",
            "json",
        ],
        db_path,
    )
    assert result.returncode == 0
    added = json.loads(result.stdout)
    assert added["title"] == "会議準備"
    assert added["status"] == "doing"
    assert added["due_date"] == "2025-12-15"
    todo_id = added["id"]

    # リスト確認
    result = run_cli(["list", "--format", "json"], db_path)
    assert result.returncode == 0
    items = json.loads(result.stdout)
    assert len(items) == 1
    assert items[0]["id"] == todo_id


def test_cli_update(tmp_path):
    """TODO更新"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    result = run_cli(
        ["add", "--title", "買い物", "--format", "json"],
        db_path,
    )
    assert result.returncode == 0
    todo_id = json.loads(result.stdout)["id"]

    # 更新
    result = run_cli(
        [
            "update",
            "--id",
            str(todo_id),
            "--title",
            "買い物（牛乳とパン）",
            "--description",
            "スーパーで購入",
            "--status",
            "done",
            "--format",
            "json",
        ],
        db_path,
    )
    assert result.returncode == 0
    updated = json.loads(result.stdout)
    assert updated["title"] == "買い物（牛乳とパン）"
    assert updated["description"] == "スーパーで購入"
    assert updated["status"] == "done"


def test_cli_complete(tmp_path):
    """TODO完了"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    result = run_cli(["add", "--title", "タスクA", "--format", "json"], db_path)
    assert result.returncode == 0
    todo_id = json.loads(result.stdout)["id"]

    # 完了
    result = run_cli(["complete", "--id", str(todo_id), "--format", "json"], db_path)
    assert result.returncode == 0
    completed = json.loads(result.stdout)
    assert completed["status"] == "done"


def test_cli_delete(tmp_path):
    """TODO削除"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    result = run_cli(["add", "--title", "タスクB", "--format", "json"], db_path)
    assert result.returncode == 0
    todo_id = json.loads(result.stdout)["id"]

    # 削除
    result = run_cli(["delete", "--id", str(todo_id), "--format", "json"], db_path)
    assert result.returncode == 0
    deleted_info = json.loads(result.stdout)
    assert deleted_info["deleted"] is True
    assert deleted_info["id"] == todo_id

    # リスト確認（空）
    result = run_cli(["list", "--format", "json"], db_path)
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_cli_get(tmp_path):
    """特定TODO取得"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    result = run_cli(
        ["add", "--title", "確認用タスク", "--description", "詳細情報", "--format", "json"],
        db_path,
    )
    assert result.returncode == 0
    todo_id = json.loads(result.stdout)["id"]

    # 取得
    result = run_cli(["get", "--id", str(todo_id), "--format", "json"], db_path)
    assert result.returncode == 0
    todo = json.loads(result.stdout)
    assert todo["id"] == todo_id
    assert todo["title"] == "確認用タスク"
    assert todo["description"] == "詳細情報"


def test_cli_update_clear_due_date(tmp_path):
    """期限日クリア"""
    db_path = tmp_path / "cli_test.db"

    # 追加（期限あり）
    result = run_cli(
        ["add", "--title", "期限テスト", "--due-date", "2025-12-31", "--format", "json"],
        db_path,
    )
    assert result.returncode == 0
    todo_id = json.loads(result.stdout)["id"]
    assert json.loads(result.stdout)["due_date"] == "2025-12-31"

    # 期限クリア
    result = run_cli(
        ["update", "--id", str(todo_id), "--clear-due-date", "--format", "json"],
        db_path,
    )
    assert result.returncode == 0
    updated = json.loads(result.stdout)
    assert updated["due_date"] is None


def test_cli_error_invalid_id(tmp_path):
    """存在しないID指定でエラー"""
    db_path = tmp_path / "cli_test.db"

    result = run_cli(["get", "--id", "999", "--format", "json"], db_path)
    assert result.returncode == 1
    assert "見つかりません" in result.stderr


def test_cli_text_format(tmp_path):
    """テキスト形式出力"""
    db_path = tmp_path / "cli_test.db"

    # 追加
    run_cli(["add", "--title", "テキストテスト", "--description", "説明文"], db_path)

    # リスト（テキスト）
    result = run_cli(["list", "--format", "text"], db_path)
    assert result.returncode == 0
    assert "テキストテスト" in result.stdout
    assert "説明文" in result.stdout
