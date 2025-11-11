#!/usr/bin/env python3
"""
TODO管理CLI - AI秘書がsubprocess経由で呼び出すコマンドラインインターフェース

Usage:
    python -m src.todo.cli list [--format json|text]
    python -m src.todo.cli add --title "タイトル" [--description "詳細"] [--due-date YYYY-MM-DD] [--status pending|in_progress|done]
    python -m src.todo.cli update --id ID [--title "新タイトル"] [--description "新詳細"] [--due-date YYYY-MM-DD] [--status pending|in_progress|done] [--clear-due-date]
    python -m src.todo.cli complete --id ID
    python -m src.todo.cli delete --id ID
    python -m src.todo.cli get --id ID [--format json|text]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Dict, List, Optional

from .models import TodoItem, TodoStatus
from .repository import TodoRepository, UNSET


def format_todo_text(todo: TodoItem) -> str:
    """Todoアイテムをテキスト形式で整形"""
    due = todo.due_date or "未設定"
    description = todo.description.strip() or "説明なし"
    return f"[{todo.id}] {todo.status.value} | 期限: {due} | {todo.title} | {description}"


def format_todo_json(todo: TodoItem) -> Dict[str, Any]:
    """Todoアイテムを辞書形式に変換"""
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "status": todo.status.value,
        "due_date": todo.due_date,
        "created_at": todo.created_at,
        "updated_at": todo.updated_at,
    }


def cmd_list(repo: TodoRepository, output_format: str) -> int:
    """Todoリストを表示"""
    items = repo.list()
    if output_format == "json":
        print(json.dumps([format_todo_json(item) for item in items], ensure_ascii=False))
    else:
        if not items:
            print("TODOは登録されていません。")
        else:
            for item in items:
                print(format_todo_text(item))
    return 0


def cmd_add(
    repo: TodoRepository,
    title: str,
    description: str,
    due_date: Optional[str],
    status: str,
    output_format: str,
) -> int:
    """新しいTodoを追加"""
    if not title.strip():
        print("Error: タイトルは必須です。", file=sys.stderr)
        return 1

    try:
        todo_status = TodoStatus(status)
    except ValueError:
        print(
            f"Error: 不正なstatus値: {status}。pending|in_progress|doneのいずれかを指定してください。",
            file=sys.stderr,
        )
        return 1

    try:
        created = repo.create(
            title=title.strip(),
            description=description.strip(),
            due_date=due_date,
            status=todo_status,
        )
        if output_format == "json":
            print(json.dumps(format_todo_json(created), ensure_ascii=False))
        else:
            print(f"追加しました: {format_todo_text(created)}")
        return 0
    except Exception as exc:
        print(f"Error: TODO追加に失敗しました: {exc}", file=sys.stderr)
        return 1


def cmd_update(
    repo: TodoRepository,
    todo_id: int,
    title: Optional[str],
    description: Optional[str],
    due_date: Optional[str],
    status: Optional[str],
    clear_due_date: bool,
    output_format: str,
) -> int:
    """既存のTodoを更新"""
    try:
        todo_status = TodoStatus(status) if status else None
    except ValueError:
        print(
            f"Error: 不正なstatus値: {status}。pending|in_progress|doneのいずれかを指定してください。",
            file=sys.stderr,
        )
        return 1

    due_date_value = UNSET
    if clear_due_date:
        due_date_value = None
    elif due_date is not None:
        due_date_value = due_date

    try:
        updated = repo.update(
            todo_id,
            title=title.strip() if title else None,
            description=description.strip() if description else None,
            due_date=due_date_value,
            status=todo_status,
        )
        if not updated:
            print(f"Error: ID {todo_id} のTODOが見つかりません。", file=sys.stderr)
            return 1

        if output_format == "json":
            print(json.dumps(format_todo_json(updated), ensure_ascii=False))
        else:
            print(f"更新しました: {format_todo_text(updated)}")
        return 0
    except Exception as exc:
        print(f"Error: TODO更新に失敗しました: {exc}", file=sys.stderr)
        return 1


def cmd_complete(repo: TodoRepository, todo_id: int, output_format: str) -> int:
    """Todoを完了状態にする"""
    try:
        updated = repo.update(todo_id, status=TodoStatus.DONE)
        if not updated:
            print(f"Error: ID {todo_id} のTODOが見つかりません。", file=sys.stderr)
            return 1

        if output_format == "json":
            print(json.dumps(format_todo_json(updated), ensure_ascii=False))
        else:
            print(f"完了しました: {format_todo_text(updated)}")
        return 0
    except Exception as exc:
        print(f"Error: TODO完了処理に失敗しました: {exc}", file=sys.stderr)
        return 1


def cmd_delete(repo: TodoRepository, todo_id: int, output_format: str) -> int:
    """Todoを削除"""
    try:
        deleted = repo.delete(todo_id)
        if not deleted:
            print(f"Error: ID {todo_id} のTODOが見つかりません。", file=sys.stderr)
            return 1

        if output_format == "json":
            print(json.dumps({"deleted": True, "id": todo_id}, ensure_ascii=False))
        else:
            print(f"削除しました: ID {todo_id}")
        return 0
    except Exception as exc:
        print(f"Error: TODO削除に失敗しました: {exc}", file=sys.stderr)
        return 1


def cmd_get(repo: TodoRepository, todo_id: int, output_format: str) -> int:
    """特定のTodoを取得"""
    try:
        todo = repo.get(todo_id)
        if not todo:
            print(f"Error: ID {todo_id} のTODOが見つかりません。", file=sys.stderr)
            return 1

        if output_format == "json":
            print(json.dumps(format_todo_json(todo), ensure_ascii=False))
        else:
            print(format_todo_text(todo))
        return 0
    except Exception as exc:
        print(f"Error: TODO取得に失敗しました: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    """CLIエントリポイント"""
    parser = argparse.ArgumentParser(
        description="TODO管理CLI - AI秘書がsubprocess経由で呼び出すインターフェース",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="SQLiteデータベースファイルのパス（デフォルト: data/todo.db）",
    )

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド", required=True)

    # list コマンド
    parser_list = subparsers.add_parser("list", help="TODOリストを表示")
    parser_list.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    # add コマンド
    parser_add = subparsers.add_parser("add", help="新しいTODOを追加")
    parser_add.add_argument("--title", required=True, help="TODOのタイトル")
    parser_add.add_argument("--description", default="", help="TODOの詳細説明")
    parser_add.add_argument("--due-date", help="期限日（YYYY-MM-DD形式）")
    parser_add.add_argument(
        "--status",
        choices=["pending", "in_progress", "done"],
        default="pending",
        help="初期ステータス（デフォルト: pending）",
    )
    parser_add.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    # update コマンド
    parser_update = subparsers.add_parser("update", help="既存のTODOを更新")
    parser_update.add_argument("--id", type=int, required=True, help="更新するTODOのID")
    parser_update.add_argument("--title", help="新しいタイトル")
    parser_update.add_argument("--description", help="新しい詳細説明")
    parser_update.add_argument("--due-date", help="新しい期限日（YYYY-MM-DD形式）")
    parser_update.add_argument("--clear-due-date", action="store_true", help="期限日をクリア")
    parser_update.add_argument(
        "--status",
        choices=["pending", "in_progress", "done"],
        help="新しいステータス",
    )
    parser_update.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    # complete コマンド
    parser_complete = subparsers.add_parser("complete", help="TODOを完了状態にする")
    parser_complete.add_argument("--id", type=int, required=True, help="完了するTODOのID")
    parser_complete.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    # delete コマンド
    parser_delete = subparsers.add_parser("delete", help="TODOを削除")
    parser_delete.add_argument("--id", type=int, required=True, help="削除するTODOのID")
    parser_delete.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    # get コマンド
    parser_get = subparsers.add_parser("get", help="特定のTODOを取得")
    parser_get.add_argument("--id", type=int, required=True, help="取得するTODOのID")
    parser_get.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="出力フォーマット（デフォルト: text）",
    )

    args = parser.parse_args()

    # リポジトリ初期化
    repo = TodoRepository(db_path=args.db_path if args.db_path else None)

    # コマンド実行
    if args.command == "list":
        return cmd_list(repo, args.format)
    elif args.command == "add":
        return cmd_add(
            repo,
            args.title,
            args.description,
            args.due_date,
            args.status,
            args.format,
        )
    elif args.command == "update":
        return cmd_update(
            repo,
            args.id,
            args.title,
            args.description,
            args.due_date,
            args.status,
            args.clear_due_date,
            args.format,
        )
    elif args.command == "complete":
        return cmd_complete(repo, args.id, args.format)
    elif args.command == "delete":
        return cmd_delete(repo, args.id, args.format)
    elif args.command == "get":
        return cmd_get(repo, args.id, args.format)
    else:
        print(f"Error: 不明なコマンド: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
