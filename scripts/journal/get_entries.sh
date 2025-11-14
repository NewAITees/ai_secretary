#!/bin/bash
# ジャーナルエントリ取得スクリプト

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

# デフォルトは今日の日付
DATE="${1:-$(date +%Y-%m-%d)}"

# JSON配列で返す
sqlite3 "$DB_PATH" <<EOF
SELECT COALESCE(json_group_array(
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
), '[]') FROM journal_entries j
WHERE date(j.occurred_at) = '$DATE'
ORDER BY j.occurred_at DESC;
EOF
