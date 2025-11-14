#!/bin/bash
# 既存todosテーブルをtodo_itemsに移行

set -euo pipefail

OLD_DB="${AI_SECRETARY_TODO_DB_PATH:-data/todo.db}"
NEW_DB="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

if [ ! -f "$OLD_DB" ]; then
    echo "No existing TODO database found at $OLD_DB"
    echo "Skipping migration."
    exit 0
fi

# 新DB初期化（統合スキーマ）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/init_db.sh"

# データ移行（status値のマッピング: pending→todo, in_progress→doing, done→done）
sqlite3 "$NEW_DB" <<EOF
-- 外部DBから読み込む（ATTACH使用）
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
