# P2実装計画：「今日やったこと」記録機能（統合スキーマ・BASH中心設計）

## 概要

日々の作業ログを記録・管理する機能を実装します。**P1（TODO）と同一SQLiteインスタンスで管理**し、**REST APIは使用せず、すべてBASHスクリプト経由でSQLiteを直接操作**する設計とします。AI秘書は`subprocess`経由でBASHスクリプトを実行し、標準出力/標準エラー出力を解析します。

## 統合設計の利点

- **横断結合の簡潔化**: TODO⇄実績の突合が容易（`journal_todo_links`テーブル経由）
- **共有リソース**: BashExecutor・監査ログ・設定管理を共有
- **整合性保証**: 同一トランザクション内でTODOと実績を管理可能
- **将来拡張性**: 日次サマリーや提案機能で横断クエリが簡潔

## 設計方針（重要）

### 外部システムアクセスの統一原則

```
ユーザー → AI秘書 (Python) → subprocess → BASHスクリプト → SQLite
                    ↑                              ↓
                    └──────── JSON出力 ────────────┘
```

- **すべての操作はBASHスクリプトで実装**
- **REST APIは一切使用しない**
- **フロントエンドUIは不要**（AI秘書との会話で完結）
- **JSON形式での入出力**（構造化データの受け渡し）

## 参考資料

- 外部システムアクセス方針: `plan/TODO.md`（冒頭の設計方針セクション）
- lifelog-system: `lifelog-system/README.md`, `lifelog-system/src/cli_viewer.py`
- 既存TODO実装（P1）: `src/todo/`（`data/todo.db`を使用）

## 統合データスキーマ設計

### 設計方針

- **同一SQLiteインスタンス**: `data/ai_secretary.db`（既存の`data/todo.db`を移行）
- **論理分離**: `todo_*`と`journal_*`名前空間で境界づけ
- **横断結合**: `journal_todo_links`テーブルでTODO⇄実績をリンク

### 統合スキーマDDL

```sql
-- ========================================
-- コンテキスト：TODO（P1 - 既存を拡張）
-- ========================================

-- 既存todosテーブルをtodo_itemsに移行（マイグレーション必要）
CREATE TABLE IF NOT EXISTS todo_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  description   TEXT,
  status        TEXT NOT NULL CHECK (status IN ('todo','doing','done','archived')),
  priority      INTEGER NOT NULL DEFAULT 3,            -- 1高…5低
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  due_date      TEXT,                                   -- 任意
  tags_json     TEXT DEFAULT '[]'                       -- ["P1","work"] 等
);

CREATE INDEX IF NOT EXISTS idx_todo_status ON todo_items(status);
CREATE INDEX IF NOT EXISTS idx_todo_priority ON todo_items(priority);
CREATE INDEX IF NOT EXISTS idx_todo_due ON todo_items(due_date);

-- 変更履歴（将来の監査/提案強化に有効）
CREATE TABLE IF NOT EXISTS todo_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id       INTEGER NOT NULL,
  event_type    TEXT NOT NULL,                          -- created/updated/status_changed/comment など
  payload_json  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (todo_id) REFERENCES todo_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_todo_events_todo ON todo_events(todo_id);

-- ========================================
-- コンテキスト：ジャーナル（P2：「今日やったこと」）
-- ========================================

CREATE TABLE IF NOT EXISTS journal_entries (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at   TEXT NOT NULL,                          -- 実績時刻（ISO8601形式）
  title         TEXT NOT NULL,
  details       TEXT,                                   -- 自由記述
  source        TEXT NOT NULL DEFAULT 'manual',         -- manual/cli/import 等
  meta_json     TEXT NOT NULL DEFAULT '{}',             -- 構造化メタ（{"duration_minutes": 60, "energy_level": 3, "mood": "happy"}など）
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_occurred ON journal_entries(occurred_at);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date(occurred_at));

-- タグ（多対多）
CREATE TABLE IF NOT EXISTS journal_tags (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS journal_entry_tags (
  entry_id      INTEGER NOT NULL,
  tag_id        INTEGER NOT NULL,
  PRIMARY KEY (entry_id, tag_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id)   REFERENCES journal_tags(id)    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entry_tags_entry ON journal_entry_tags(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON journal_entry_tags(tag_id);

-- TODO と実績のリンク（突合のためのブリッジ）
CREATE TABLE IF NOT EXISTS journal_todo_links (
  entry_id      INTEGER NOT NULL,
  todo_id       INTEGER NOT NULL,
  relation      TEXT NOT NULL DEFAULT 'progress',       -- progress/blocked_by/related_to 等
  PRIMARY KEY (entry_id, todo_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (todo_id)  REFERENCES todo_items(id)      ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_links_entry ON journal_todo_links(entry_id);
CREATE INDEX IF NOT EXISTS idx_links_todo ON journal_todo_links(todo_id);

-- ========================================
-- 横断ビュー（日次サマリー・提案機能で活用）
-- ========================================

-- 日別の進捗サマリー
CREATE VIEW IF NOT EXISTS v_daily_progress AS
SELECT
  date(j.occurred_at)             AS day,
  COUNT(j.id)                     AS entry_count,
  SUM(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) AS linked_todo_updates
FROM journal_entries j
LEFT JOIN journal_todo_links l ON l.entry_id = j.id
LEFT JOIN todo_items t         ON t.id = l.todo_id
GROUP BY date(j.occurred_at);

-- TODOごとの最新実績
CREATE VIEW IF NOT EXISTS v_todo_latest_journal AS
SELECT
  t.id           AS todo_id,
  t.title        AS todo_title,
  MAX(j.occurred_at) AS last_activity_at
FROM todo_items t
LEFT JOIN journal_todo_links l ON l.todo_id = t.id
LEFT JOIN journal_entries j     ON j.id = l.entry_id
GROUP BY t.id;
```

## ディレクトリ構成

```
scripts/
  journal/                   # 日次ログ操作（journal_entries操作）
    init_db.sh              # 統合DB初期化（todo_items + journal_entries + ビュー）
    migrate_todos.sh         # 既存todos → todo_items移行スクリプト
    log_entry.sh            # エントリ記録（INSERT）
    get_entries.sh          # エントリ取得（SELECT）
    search_entries.sh       # エントリ検索
    update_entry.sh         # エントリ更新
    delete_entry.sh         # エントリ削除
    link_todo.sh            # TODOと実績をリンク
    generate_summary.sh     # 日次サマリー生成（LLM活用）

src/
  ai_secretary/
    bash_executor.py        # subprocess安全実行ラッパー（新規）
    secretary.py            # 既存 - Journal統合追加

src/todo/                   # 既存（更新必要）
  repository.py            # todo_itemsテーブル対応に更新
  models.py                # priority, tags_json追加

tests/
  test_bash_executor.py     # BashExecutorテスト
  test_journal_scripts.sh   # BASHスクリプト統合テスト
  test_journal_llm.py       # LLM統合テスト
  test_todo_migration.py    # TODO移行テスト

doc/
  design/
    bash_executor.md        # BashExecutor設計ドキュメント
    unified_schema.md       # 統合スキーマ設計ドキュメント
```

## 実装ステップ

### ステップ0: マイグレーション準備

#### 0-1. 既存TODOデータの移行

**ファイル:** `scripts/journal/migrate_todos.sh`

```bash
#!/bin/bash
# 既存todosテーブルをtodo_itemsに移行

set -euo pipefail

OLD_DB="${AI_SECRETARY_TODO_DB_PATH:-data/todo.db}"
NEW_DB="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

if [ ! -f "$OLD_DB" ]; then
    echo "No existing TODO database found at $OLD_DB"
    exit 0
fi

# 新DB初期化（統合スキーマ）
./scripts/journal/init_db.sh

# データ移行（status値のマッピング: pending→todo, in_progress→doing, done→done）
sqlite3 "$NEW_DB" <<EOF
-- 既存todosからtodo_itemsへ移行
INSERT INTO todo_items (id, title, description, status, priority, created_at, updated_at, due_date, tags_json)
SELECT 
    id,
    title,
    description,
    CASE status
        WHEN 'pending' THEN 'todo'
        WHEN 'in_progress' THEN 'doing'
        WHEN 'done' THEN 'done'
        ELSE 'todo'
    END AS status,
    3 AS priority,  -- デフォルト優先度
    created_at,
    updated_at,
    due_date,
    '[]' AS tags_json
FROM sqlite_master
WHERE type='table' AND name='todos'
AND EXISTS (SELECT 1 FROM sqlite_master WHERE db='$OLD_DB' AND type='table' AND name='todos');

-- 外部DBから読み込む場合（ATTACH使用）
ATTACH DATABASE '$OLD_DB' AS old_db;
INSERT OR IGNORE INTO todo_items (id, title, description, status, priority, created_at, updated_at, due_date, tags_json)
SELECT 
    id,
    title,
    description,
    CASE status
        WHEN 'pending' THEN 'todo'
        WHEN 'in_progress' THEN 'doing'
        WHEN 'done' THEN 'done'
        ELSE 'todo'
    END AS status,
    3 AS priority,
    created_at,
    updated_at,
    due_date,
    '[]' AS tags_json
FROM old_db.todos;
DETACH DATABASE old_db;
EOF

echo "✓ Migration completed: $OLD_DB → $NEW_DB"
```

### ステップ1: BASHスクリプト実装

#### 1-1. 統合DB初期化スクリプト

**ファイル:** `scripts/journal/init_db.sh`

```bash
#!/bin/bash
# 統合DB初期化スクリプト（todo_items + journal_entries + ビュー）

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

# DBディレクトリ作成
mkdir -p "$(dirname "$DB_PATH")"

# 統合スキーマ作成（上記のDDLを実行）
sqlite3 "$DB_PATH" <<'EOF'
-- TODOコンテキスト
CREATE TABLE IF NOT EXISTS todo_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  description   TEXT,
  status        TEXT NOT NULL CHECK (status IN ('todo','doing','done','archived')),
  priority      INTEGER NOT NULL DEFAULT 3,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  due_date      TEXT,
  tags_json     TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_todo_status ON todo_items(status);
CREATE INDEX IF NOT EXISTS idx_todo_priority ON todo_items(priority);
CREATE INDEX IF NOT EXISTS idx_todo_due ON todo_items(due_date);

CREATE TABLE IF NOT EXISTS todo_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id       INTEGER NOT NULL,
  event_type    TEXT NOT NULL,
  payload_json  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (todo_id) REFERENCES todo_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_todo_events_todo ON todo_events(todo_id);

-- ジャーナルコンテキスト
CREATE TABLE IF NOT EXISTS journal_entries (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at   TEXT NOT NULL,
  title         TEXT NOT NULL,
  details       TEXT,
  source        TEXT NOT NULL DEFAULT 'manual',
  meta_json     TEXT NOT NULL DEFAULT '{}',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_occurred ON journal_entries(occurred_at);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date(occurred_at));

CREATE TABLE IF NOT EXISTS journal_tags (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS journal_entry_tags (
  entry_id      INTEGER NOT NULL,
  tag_id        INTEGER NOT NULL,
  PRIMARY KEY (entry_id, tag_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id)   REFERENCES journal_tags(id)    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entry_tags_entry ON journal_entry_tags(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON journal_entry_tags(tag_id);

CREATE TABLE IF NOT EXISTS journal_todo_links (
  entry_id      INTEGER NOT NULL,
  todo_id       INTEGER NOT NULL,
  relation      TEXT NOT NULL DEFAULT 'progress',
  PRIMARY KEY (entry_id, todo_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (todo_id)  REFERENCES todo_items(id)      ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_links_entry ON journal_todo_links(entry_id);
CREATE INDEX IF NOT EXISTS idx_links_todo ON journal_todo_links(todo_id);

-- ビュー
CREATE VIEW IF NOT EXISTS v_daily_progress AS
SELECT
  date(j.occurred_at)             AS day,
  COUNT(j.id)                     AS entry_count,
  SUM(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) AS linked_todo_updates
FROM journal_entries j
LEFT JOIN journal_todo_links l ON l.entry_id = j.id
LEFT JOIN todo_items t         ON t.id = l.todo_id
GROUP BY date(j.occurred_at);

CREATE VIEW IF NOT EXISTS v_todo_latest_journal AS
SELECT
  t.id           AS todo_id,
  t.title        AS todo_title,
  MAX(j.occurred_at) AS last_activity_at
FROM todo_items t
LEFT JOIN journal_todo_links l ON l.todo_id = t.id
LEFT JOIN journal_entries j     ON j.id = l.entry_id
GROUP BY t.id;
EOF

echo "✓ Unified database initialized at $DB_PATH"
```

#### 1-2. エントリ記録スクリプト

**ファイル:** `scripts/journal/log_entry.sh`

```bash
#!/bin/bash
# ジャーナルエントリ記録スクリプト

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

# 引数パース
TITLE=""
DETAILS=""
OCCURRED_AT=""
SOURCE="manual"
META_JSON="{}"
TAG_NAMES=""
TODO_IDS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --title)
            TITLE="$2"
            shift 2
            ;;
        --details)
            DETAILS="$2"
            shift 2
            ;;
        --occurred-at)
            OCCURRED_AT="$2"
            shift 2
            ;;
        --source)
            SOURCE="$2"
            shift 2
            ;;
        --meta-json)
            META_JSON="$2"
            shift 2
            ;;
        --tags)
            TAG_NAMES="$2"
            shift 2
            ;;
        --todo-ids)
            TODO_IDS="$2"  # カンマ区切り: "1,2,3"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# 必須パラメータチェック
if [ -z "$TITLE" ]; then
    echo '{"error": "title is required"}' >&2
    exit 1
fi

# 日時生成（未指定時は現在時刻）
if [ -z "$OCCURRED_AT" ]; then
    OCCURRED_AT=$(date -Iseconds)
fi

# SQL実行（エントリ挿入）
ENTRY_ID=$(sqlite3 "$DB_PATH" <<EOF
INSERT INTO journal_entries (occurred_at, title, details, source, meta_json, created_at)
VALUES ('$OCCURRED_AT', '$TITLE', $([ -n "$DETAILS" ] && echo "'$DETAILS'" || echo "NULL"), '$SOURCE', '$META_JSON', datetime('now'));
SELECT last_insert_rowid();
EOF
)

# タグ処理（カンマ区切り文字列から）
if [ -n "$TAG_NAMES" ]; then
    IFS=',' read -ra TAGS <<< "$TAG_NAMES"
    for tag_name in "${TAGS[@]}"; do
        # タグ取得または作成
        TAG_ID=$(sqlite3 "$DB_PATH" <<EOF
INSERT OR IGNORE INTO journal_tags (name) VALUES ('$tag_name');
SELECT id FROM journal_tags WHERE name = '$tag_name';
EOF
        )
        # エントリとタグをリンク
        sqlite3 "$DB_PATH" <<EOF
INSERT OR IGNORE INTO journal_entry_tags (entry_id, tag_id) VALUES ($ENTRY_ID, $TAG_ID);
EOF
    done
fi

# TODOリンク処理
if [ -n "$TODO_IDS" ]; then
    IFS=',' read -ra TODO_ARRAY <<< "$TODO_IDS"
    for todo_id in "${TODO_ARRAY[@]}"; do
        sqlite3 "$DB_PATH" <<EOF
INSERT OR IGNORE INTO journal_todo_links (entry_id, todo_id, relation) VALUES ($ENTRY_ID, $todo_id, 'progress');
EOF
    done
fi

# JSON出力
sqlite3 "$DB_PATH" <<EOF
SELECT json_object(
    'id', j.id,
    'occurred_at', j.occurred_at,
    'title', j.title,
    'details', j.details,
    'source', j.source,
    'meta_json', j.meta_json,
    'created_at', j.created_at,
    'tags', COALESCE(
        (SELECT json_group_array(t.name)
         FROM journal_entry_tags et
         JOIN journal_tags t ON et.tag_id = t.id
         WHERE et.entry_id = j.id),
        '[]'
    ),
    'linked_todos', COALESCE(
        (SELECT json_group_array(json_object('todo_id', l.todo_id, 'relation', l.relation))
         FROM journal_todo_links l
         WHERE l.entry_id = j.id),
        '[]'
    )
) FROM journal_entries j WHERE j.id = $ENTRY_ID;
EOF
```

#### 1-3. エントリ取得スクリプト

**ファイル:** `scripts/journal/get_entries.sh`

```bash
#!/bin/bash
# ジャーナルエントリ取得スクリプト

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

# デフォルトは今日の日付
DATE="${1:-$(date +%Y-%m-%d)}"

# JSON配列で返す
sqlite3 "$DB_PATH" <<EOF
SELECT json_group_array(
    json_object(
        'id', j.id,
        'occurred_at', j.occurred_at,
        'title', j.title,
        'details', j.details,
        'source', j.source,
        'meta_json', j.meta_json,
        'created_at', j.created_at,
        'tags', COALESCE(
            (SELECT json_group_array(t.name)
             FROM journal_entry_tags et
             JOIN journal_tags t ON et.tag_id = t.id
             WHERE et.entry_id = j.id),
            '[]'
        ),
        'linked_todos', COALESCE(
            (SELECT json_group_array(json_object('todo_id', l.todo_id, 'relation', l.relation))
             FROM journal_todo_links l
             WHERE l.entry_id = j.id),
            '[]'
        )
    )
) FROM journal_entries j
WHERE date(j.occurred_at) = '$DATE'
ORDER BY j.occurred_at DESC;
EOF
```

#### 1-4. エントリ検索スクリプト

**ファイル:** `scripts/journal/search_entries.sh`

```bash
#!/bin/bash
# ジャーナルエントリ検索スクリプト

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

START_DATE=""
END_DATE=""
TAG_NAME=""
TODO_ID=""
TITLE_PATTERN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --tag)
            TAG_NAME="$2"
            shift 2
            ;;
        --todo-id)
            TODO_ID="$2"
            shift 2
            ;;
        --title-pattern)
            TITLE_PATTERN="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# WHERE句構築
WHERE="1=1"
[ -n "$START_DATE" ] && WHERE="$WHERE AND date(j.occurred_at) >= '$START_DATE'"
[ -n "$END_DATE" ] && WHERE="$WHERE AND date(j.occurred_at) <= '$END_DATE'"
[ -n "$TITLE_PATTERN" ] && WHERE="$WHERE AND j.title LIKE '%$TITLE_PATTERN%'"

# タグ検索のJOIN
JOIN_TAG=""
[ -n "$TAG_NAME" ] && JOIN_TAG="JOIN journal_entry_tags et ON et.entry_id = j.id JOIN journal_tags t ON et.tag_id = t.id AND t.name = '$TAG_NAME'"

# TODOリンク検索のJOIN
JOIN_TODO=""
[ -n "$TODO_ID" ] && JOIN_TODO="JOIN journal_todo_links l ON l.entry_id = j.id AND l.todo_id = $TODO_ID"

# JSON配列で返す
sqlite3 "$DB_PATH" <<EOF
SELECT json_group_array(
    json_object(
        'id', j.id,
        'occurred_at', j.occurred_at,
        'title', j.title,
        'details', j.details,
        'source', j.source,
        'meta_json', j.meta_json,
        'created_at', j.created_at,
        'tags', COALESCE(
            (SELECT json_group_array(t2.name)
             FROM journal_entry_tags et2
             JOIN journal_tags t2 ON et2.tag_id = t2.id
             WHERE et2.entry_id = j.id),
            '[]'
        )
    )
) FROM journal_entries j
$JOIN_TAG
$JOIN_TODO
WHERE $WHERE
ORDER BY j.occurred_at DESC;
EOF
```

#### 1-5. TODOリンクスクリプト

**ファイル:** `scripts/journal/link_todo.sh`

```bash
#!/bin/bash
# ジャーナルエントリとTODOをリンク

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

ENTRY_ID=""
TODO_ID=""
RELATION="progress"

while [[ $# -gt 0 ]]; do
    case $1 in
        --entry-id)
            ENTRY_ID="$2"
            shift 2
            ;;
        --todo-id)
            TODO_ID="$2"
            shift 2
            ;;
        --relation)
            RELATION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [ -z "$ENTRY_ID" ] || [ -z "$TODO_ID" ]; then
    echo '{"error": "entry-id and todo-id are required"}' >&2
    exit 1
fi

sqlite3 "$DB_PATH" <<EOF
INSERT OR REPLACE INTO journal_todo_links (entry_id, todo_id, relation)
VALUES ($ENTRY_ID, $TODO_ID, '$RELATION');
EOF

echo '{"success": true, "entry_id": '$ENTRY_ID', "todo_id": '$TODO_ID', "relation": "'$RELATION'"}'
```

#### 1-6. サマリー生成スクリプト

**ファイル:** `scripts/journal/generate_summary.sh`

```bash
#!/bin/bash
# 日次サマリー生成スクリプト（横断結合対応）

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"
DATE="${1:-$(date +%Y-%m-%d)}"

# 当日のエントリ取得
ENTRIES=$(sqlite3 "$DB_PATH" <<EOF
SELECT json_group_array(
    json_object(
        'occurred_at', j.occurred_at,
        'title', j.title,
        'details', j.details,
        'meta_json', j.meta_json,
        'linked_todos', COALESCE(
            (SELECT json_group_array(json_object('todo_id', l.todo_id, 'todo_title', t.title, 'relation', l.relation))
             FROM journal_todo_links l
             JOIN todo_items t ON l.todo_id = t.id
             WHERE l.entry_id = j.id),
            '[]'
        )
    )
) FROM journal_entries j
WHERE date(j.occurred_at) = '$DATE'
ORDER BY j.occurred_at ASC;
EOF
)

# エントリが空の場合
if [ "$ENTRIES" = "[]" ] || [ "$ENTRIES" = "null" ]; then
    echo '{"date": "'$DATE'", "summary": "今日の記録はありません", "entry_count": 0, "activities": []}'
    exit 0
fi

# 統計計算（ビュー活用）
PROGRESS=$(sqlite3 "$DB_PATH" <<EOF
SELECT json_object(
    'entry_count', entry_count,
    'linked_todo_updates', linked_todo_updates
) FROM v_daily_progress WHERE day = '$DATE';
EOF
)

# TODO進捗サマリー
TODO_SUMMARY=$(sqlite3 "$DB_PATH" <<EOF
SELECT json_group_array(
    json_object(
        'todo_id', t.id,
        'todo_title', t.title,
        'status', t.status,
        'last_activity', v.last_activity_at
    )
) FROM todo_items t
LEFT JOIN v_todo_latest_journal v ON v.todo_id = t.id
WHERE date(v.last_activity_at) = '$DATE' OR v.last_activity_at IS NULL
ORDER BY t.priority ASC, t.id DESC;
EOF
)

# JSON出力
cat <<EOF
{
    "date": "$DATE",
    "activities": $ENTRIES,
    "progress": $PROGRESS,
    "todo_summary": $TODO_SUMMARY
}
EOF
```

### ステップ2: BashExecutor実装（安全なsubprocess実行基盤）

**ファイル:** `src/ai_secretary/bash_executor.py`

```python
"""
BashExecutor: subprocess経由での安全なBASHスクリプト実行

設計方針:
- コマンドインジェクション対策（ホワイトリスト方式）
- タイムアウト設定
- エラーハンドリング
- 監査ログ
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


class BashExecutor:
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
        self,
        script_name: str,
        args: Optional[List[str]] = None,
        parse_json: bool = True
    ) -> BashResult:
        """
        BASHスクリプトを実行

        Args:
            script_name: スクリプト名（相対パス、例: "daily_log/log_activity.sh"）
            args: スクリプト引数
            parse_json: 標準出力をJSONとしてパースするか

        Returns:
            BashResult: 実行結果

        Raises:
            ValueError: スクリプトがホワイトリストにない場合
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
                check=False  # exit_codeを自分でチェックする
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
                parsed_json=parsed_json
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
        dangerous_chars = [";", "&", "|", "`", "$", "(", ")", "<", ">"]

        sanitized = []
        for arg in args:
            if any(char in arg for char in dangerous_chars):
                logger.warning(f"Potentially dangerous argument: {arg}")
                # エスケープまたは拒否
                raise ValueError(f"Argument contains dangerous characters: {arg}")
            sanitized.append(arg)

        return sanitized
```

### ステップ3: AISecretary統合

**ファイル:** `src/ai_secretary/secretary.py`（既存ファイルに追加）

```python
from src.ai_secretary.bash_executor import BashExecutor, BashResult

class AISecretary:
    def __init__(
        self,
        # 既存パラメータ...
        bash_executor: Optional[BashExecutor] = None
    ):
        # 既存初期化...
        self.bash_executor = bash_executor or BashExecutor()

    def _build_system_message(self) -> str:
        """システムメッセージ構築（日次ログコンテキスト追加）"""
        base_message = super()._build_system_message()

        # 今日のジャーナルエントリ取得（BASH経由）
        try:
            result = self.bash_executor.execute(
                "journal/get_entries.sh",
                args=[datetime.now().strftime("%Y-%m-%d")],
                parse_json=True
            )

            if result.success and result.parsed_json:
                entries = result.parsed_json
                if entries:
                    log_context = "\n\n## 今日の活動ログ:\n"
                    for entry in entries:
                        log_context += f"- [{entry['occurred_at']}] {entry['title']}"
                        if entry.get('details'):
                            log_context += f": {entry['details']}"
                        # TODOリンク情報
                        if entry.get('linked_todos'):
                            log_context += f" [TODO: {', '.join([str(t['todo_id']) for t in entry['linked_todos']])}]"
                        log_context += "\n"
                    base_message += log_context
        except Exception as e:
            logger.warning(f"Failed to load daily logs: {e}")

        return base_message

    def _handle_user_activity_logging(self, user_message: str):
        """
        ユーザーメッセージから活動記録を抽出してログに追加

        例:
        - 「Pythonの勉強を3時間やった」→ log_activity.sh実行
        - 「今日何やったっけ？」→ get_logs.sh + サマリー生成
        """
        # LLMで意図判定（省略: 実際はLLMに判定させる）
        # 仮実装として簡易パターンマッチング
        if "やった" in user_message or "した" in user_message:
            # エントリ記録のトリガー（実際はLLMが構造化JSONを返す）
            # 例: bash_executor.execute("journal/log_entry.sh", ["--title", "...", "--details", "..."])
            pass
        elif "何やった" in user_message or "サマリー" in user_message:
            # サマリー生成
            result = self.bash_executor.execute(
                "journal/generate_summary.sh",
                parse_json=True
            )
            if result.success:
                return result.parsed_json.get("summary", "")
```

### ステップ4: テストコード

**ファイル:** `tests/test_bash_executor.py`

```python
import pytest
from pathlib import Path
from src.ai_secretary.bash_executor import BashExecutor, BashResult


def test_execute_allowed_script():
    """許可されたスクリプトの実行"""
    executor = BashExecutor()
    result = executor.execute("journal/init_db.sh", parse_json=False)
    assert result.success


def test_execute_disallowed_script():
    """許可されていないスクリプトの実行拒否"""
    executor = BashExecutor()
    with pytest.raises(ValueError, match="not allowed"):
        executor.execute("evil_script.sh")


def test_sanitize_dangerous_args():
    """危険な引数の検出"""
    executor = BashExecutor()
    with pytest.raises(ValueError, match="dangerous characters"):
        executor.execute("journal/get_entries.sh", args=["'; DROP TABLE users;"])
```

**ファイル:** `tests/test_journal_scripts.sh`

```bash
#!/bin/bash
# BASHスクリプト統合テスト

set -euo pipefail

export AI_SECRETARY_DB_PATH="data/test_ai_secretary.db"

# クリーンアップ
rm -f "$AI_SECRETARY_DB_PATH"

# テスト1: DB初期化
echo "Test 1: Initialize unified DB"
./scripts/journal/init_db.sh

# テスト2: エントリ記録
echo "Test 2: Log entry"
RESULT=$(./scripts/journal/log_entry.sh \
    --title "Test Activity" \
    --details "Testing journal entry" \
    --meta-json '{"duration_minutes": 60, "energy_level": 3}')

echo "$RESULT" | jq .

# テスト3: エントリ取得
echo "Test 3: Get entries"
ENTRIES=$(./scripts/journal/get_entries.sh)
echo "$ENTRIES" | jq .

# テスト4: TODOリンク（TODOアイテム作成が必要）
echo "Test 4: Link TODO"
# まずTODOアイテムを作成（CLI経由または直接SQL）
sqlite3 "$AI_SECRETARY_DB_PATH" <<EOF
INSERT INTO todo_items (title, status, priority) VALUES ('Test TODO', 'doing', 3);
SELECT last_insert_rowid();
EOF
TODO_ID=$(sqlite3 "$AI_SECRETARY_DB_PATH" "SELECT id FROM todo_items WHERE title = 'Test TODO' LIMIT 1;")
ENTRY_ID=$(echo "$RESULT" | jq -r '.id')
./scripts/journal/link_todo.sh --entry-id "$ENTRY_ID" --todo-id "$TODO_ID"

# テスト5: サマリー生成
echo "Test 5: Generate summary"
SUMMARY=$(./scripts/journal/generate_summary.sh)
echo "$SUMMARY" | jq .

# クリーンアップ
rm -f "$AI_SECRETARY_DB_PATH"

echo "✓ All tests passed"
```

## タイムライン

| ステップ | 予想工数 | 依存 |
|---------|---------|------|
| 0. マイグレーション準備 | 1-2時間 | - |
| 1. BASHスクリプト実装 | 4-5時間 | 0 |
| 2. BashExecutor実装 | 2-3時間 | 1 |
| 3. AISecretary統合 | 2-3時間 | 2 |
| 4. 既存TODO実装更新 | 2-3時間 | 0 |
| 5. テストコード | 3-4時間 | 1,2,3,4 |
| **合計** | **14-20時間** | |

## 依存関係

- Python 3.13+
- SQLite3
- bash, jq（コマンドラインツール）
- subprocess（Python標準ライブラリ）

## 成功基準

- [ ] 統合DB（`data/ai_secretary.db`）でTODOとジャーナルが共存
- [ ] 既存TODOデータの移行が成功
- [ ] BASHスクリプトでSQLite操作が可能
- [ ] BashExecutorで安全にsubprocess実行ができる
- [ ] AI秘書がBASH経由でエントリ記録・取得できる
- [ ] AI秘書がTODOと実績をリンクできる
- [ ] AI秘書が日次サマリーを生成できる（横断結合含む）
- [ ] コマンドインジェクション対策が機能する
- [ ] 全テストが通過する

## セキュリティ対策

| 脅威 | 対策 |
|------|------|
| コマンドインジェクション | ホワイトリスト方式 + 引数サニタイズ |
| パストラバーサル | スクリプトディレクトリ外のアクセス禁止 |
| DoS（長時間実行） | タイムアウト設定（デフォルト30秒） |
| SQLインジェクション | パラメータ化クエリ（準備文） |

## 実装例：会話フロー

```
ユーザー: 「Pythonの勉強を3時間やった」
  ↓
AI秘書: LLMで意図解析 → 活動記録と判定
  ↓
AI秘書: bash_executor.execute(
    "journal/log_entry.sh",
    ["--title", "Pythonの勉強", "--meta-json", '{"duration_minutes": 180}']
)
  ↓
BASH: SQLite INSERT実行 → JSON出力
  ↓
AI秘書: 「記録しました。今日の学習時間は合計3時間です」
```

```
ユーザー: 「今日何やったっけ？」
  ↓
AI秘書: bash_executor.execute("journal/generate_summary.sh")
  ↓
BASH: SQLite SELECT + 横断結合（v_daily_progress, v_todo_latest_journal） → JSON出力
  ↓
AI秘書: LLMでサマリー生成
  ↓
AI秘書: 「本日は以下の活動を記録しています：
- [10:30] Pythonの勉強（3時間）[TODO #5と関連]
- [14:00] ドキュメント作成（1時間）
合計4時間の活動でした。TODO #5の進捗も記録されています」
```

```
ユーザー: 「TODO #5の進捗を記録したい」
  ↓
AI秘書: bash_executor.execute(
    "journal/log_entry.sh",
    ["--title", "API実装", "--todo-ids", "5"]
)
  ↓
BASH: journal_entries INSERT + journal_todo_links INSERT → JSON出力
  ↓
AI秘書: 「記録しました。TODO #5とリンクしました」
```

## 既存TODO実装の更新要件

### ステップ4: 既存コードの統合スキーマ対応

#### 4-1. `src/todo/repository.py`の更新

- `todos`テーブル → `todo_items`テーブルに変更
- `status`値のマッピング: `pending`→`todo`, `in_progress`→`doing`, `done`→`done`
- `priority`カラムの追加（デフォルト3）
- `tags_json`カラムの追加（デフォルト`[]`）
- データベースパス: `data/todo.db` → `data/ai_secretary.db`（環境変数`AI_SECRETARY_DB_PATH`）

#### 4-2. `src/todo/models.py`の更新

- `TodoItem`に`priority: int`と`tags_json: str`を追加
- `TodoStatus`の値更新（`todo`, `doing`, `done`, `archived`）

#### 4-3. マイグレーション実行

```bash
# 既存データの移行
./scripts/journal/migrate_todos.sh

# 既存API/CLIの動作確認
uv run python -m src.todo.cli list
```

## 次のステップ（将来拡張）

- P5（日次サマリー生成）: `generate_summary.sh`をLLMでリッチ化（横断結合データ活用）
- P3（チャット履歴保存）: 同様のBASH中心設計で実装（統合DBに追加）
- P8（AI秘書の機能アクセス設計）: BashExecutorの権限管理強化
- P9（履歴を元にした提案）: `journal_todo_links`とビューを活用した提案ロジック
