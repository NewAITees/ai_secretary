# TODO CLI 使い方ガイド

## 概要

AI Secretary プロジェクトのTODO管理機能は、**BASH経由で操作可能なCLI**として実装されています。これにより、AI秘書が`subprocess`経由でTODO操作を実行できます。

## 設計方針

[plan/TODO.md](../../plan/TODO.md)で定義された「外部システムアクセス方針」に基づき、すべてのTODO操作はBASHコマンドを通じて実行されます：

- AI秘書は`subprocess`経由でCLIコマンドを呼び出す
- 各コマンドは単独で実行可能
- 標準出力/標準エラー出力を解析して結果を取得
- JSON形式での入出力に対応

## 基本構成

- **実装**: [src/todo/cli.py](../../src/todo/cli.py)
- **モデル**: [src/todo/models.py](../../src/todo/models.py) - `TodoItem`, `TodoStatus`
- **リポジトリ**: [src/todo/repository.py](../../src/todo/repository.py) - SQLite操作
- **データベース**: `data/todo.db` (環境変数`AI_SECRETARY_TODO_DB_PATH`で変更可能)
- **テスト**: [tests/test_todo_cli.py](../../tests/test_todo_cli.py)

## コマンドリファレンス

### 基本構文

```bash
uv run python -m src.todo.cli [--db-path PATH] <command> [options]
```

### 共通オプション

- `--db-path PATH`: SQLiteデータベースファイルのパス（デフォルト: `data/todo.db`）
- `--format {json|text}`: 出力フォーマット（デフォルト: `text`）

---

## コマンド一覧

### 1. list - TODOリストを表示

```bash
uv run python -m src.todo.cli list [--format json|text]
```

**出力例（JSON）:**
```json
[
  {
    "id": 1,
    "title": "会議準備",
    "description": "資料作成とリハーサル",
    "status": "in_progress",
    "due_date": "2025-12-15",
    "created_at": "2025-11-11T12:00:00+00:00",
    "updated_at": "2025-11-11T12:30:00+00:00"
  }
]
```

**出力例（テキスト）:**
```
[1] in_progress | 期限: 2025-12-15 | 会議準備 | 資料作成とリハーサル
```

---

### 2. add - 新しいTODOを追加

```bash
uv run python -m src.todo.cli add \
  --title "タイトル" \
  [--description "詳細"] \
  [--due-date YYYY-MM-DD] \
  [--status pending|in_progress|done] \
  [--format json|text]
```

**例:**
```bash
uv run python -m src.todo.cli add \
  --title "買い物" \
  --description "牛乳とパンを購入" \
  --due-date 2025-12-20 \
  --status pending \
  --format json
```

**出力:**
```json
{
  "id": 2,
  "title": "買い物",
  "description": "牛乳とパンを購入",
  "status": "pending",
  "due_date": "2025-12-20",
  "created_at": "2025-11-11T14:00:00+00:00",
  "updated_at": "2025-11-11T14:00:00+00:00"
}
```

---

### 3. update - 既存のTODOを更新

```bash
uv run python -m src.todo.cli update \
  --id ID \
  [--title "新タイトル"] \
  [--description "新詳細"] \
  [--due-date YYYY-MM-DD] \
  [--status pending|in_progress|done] \
  [--clear-due-date] \
  [--format json|text]
```

**例:**
```bash
# タイトルと状態を更新
uv run python -m src.todo.cli update \
  --id 2 \
  --title "買い物（完了）" \
  --status done \
  --format json

# 期限をクリア
uv run python -m src.todo.cli update \
  --id 2 \
  --clear-due-date \
  --format json
```

---

### 4. complete - TODOを完了状態にする

```bash
uv run python -m src.todo.cli complete \
  --id ID \
  [--format json|text]
```

**例:**
```bash
uv run python -m src.todo.cli complete --id 1 --format json
```

**出力:**
```json
{
  "id": 1,
  "title": "会議準備",
  "description": "資料作成とリハーサル",
  "status": "done",
  "due_date": "2025-12-15",
  "created_at": "2025-11-11T12:00:00+00:00",
  "updated_at": "2025-11-11T15:00:00+00:00"
}
```

---

### 5. delete - TODOを削除

```bash
uv run python -m src.todo.cli delete \
  --id ID \
  [--format json|text]
```

**例:**
```bash
uv run python -m src.todo.cli delete --id 2 --format json
```

**出力:**
```json
{
  "deleted": true,
  "id": 2
}
```

---

### 6. get - 特定のTODOを取得

```bash
uv run python -m src.todo.cli get \
  --id ID \
  [--format json|text]
```

**例:**
```bash
uv run python -m src.todo.cli get --id 1 --format json
```

---

## エラーハンドリング

### 終了コード

- `0`: 成功
- `1`: エラー（標準エラー出力にメッセージ）

### エラー例

```bash
$ uv run python -m src.todo.cli get --id 999 --format json
# 終了コード: 1
# 標準エラー出力:
Error: ID 999 のTODOが見つかりません。
```

---

## AI秘書からの使用例

AI秘書は`subprocess`モジュールを使ってCLIを実行します：

```python
import subprocess
import json

# TODOリスト取得
result = subprocess.run(
    ["uv", "run", "python", "-m", "src.todo.cli", "list", "--format", "json"],
    capture_output=True,
    text=True,
    check=True
)
todos = json.loads(result.stdout)

# TODO追加
result = subprocess.run(
    [
        "uv", "run", "python", "-m", "src.todo.cli", "add",
        "--title", "レポート作成",
        "--description", "四半期報告書",
        "--due-date", "2025-12-31",
        "--status", "pending",
        "--format", "json"
    ],
    capture_output=True,
    text=True,
    check=True
)
new_todo = json.loads(result.stdout)
print(f"追加されたTODO ID: {new_todo['id']}")
```

---

## Web UI との共存

このCLIはAI秘書専用ではなく、以下の2つのインターフェースが並行して動作します：

1. **BASH CLI** (`src.todo.cli`) - AI秘書が使用
2. **FastAPI REST API** (`/api/todos`) - Web UIが使用

両者は同じ`TodoRepository`（SQLiteストレージ）を共有しているため、どちらからの操作も即座に反映されます。

---

## テスト

```bash
# CLI単体テスト
uv run pytest tests/test_todo_cli.py -v

# リポジトリテスト
uv run pytest tests/test_todo_repository.py -v

# API統合テスト
uv run pytest tests/test_todo_api.py -v

# すべて実行
uv run pytest tests/test_todo*.py -v
```

---

## 設定

### 環境変数

- `AI_SECRETARY_TODO_DB_PATH`: データベースファイルのパス（デフォルト: `data/todo.db`）

### データベース初期化

初回実行時に自動的に`data/todo.db`が作成され、必要なテーブルとインデックスが初期化されます。

---

## 関連ドキュメント

- [plan/TODO.md](../../plan/TODO.md) - 全体計画とP1タスク詳細
- [CLAUDE.md](../../CLAUDE.md) - プロジェクト概要とTODO管理の説明
- [src/todo/cli.py](../../src/todo/cli.py) - CLI実装
- [tests/test_todo_cli.py](../../tests/test_todo_cli.py) - テストコード
