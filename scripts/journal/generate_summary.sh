#!/bin/bash
# 日次サマリー生成スクリプト（横断結合対応）

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"
DATE="${1:-$(date +%Y-%m-%d)}"

# 当日のエントリ取得
ENTRIES=$(sqlite3 "$DB_PATH" <<EOF
SELECT COALESCE(json_group_array(
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
), '[]') FROM journal_entries j
WHERE date(j.occurred_at) = '$DATE'
ORDER BY j.occurred_at ASC;
EOF
)

# 統計計算（ビュー活用）
PROGRESS=$(sqlite3 "$DB_PATH" <<EOF
SELECT COALESCE(json_object(
    'entry_count', entry_count,
    'linked_todo_updates', linked_todo_updates
), '{"entry_count": 0, "linked_todo_updates": 0}')
FROM v_daily_progress WHERE day = '$DATE';
EOF
)

# TODO進捗サマリー
TODO_SUMMARY=$(sqlite3 "$DB_PATH" <<EOF
SELECT COALESCE(json_group_array(
    json_object(
        'todo_id', t.id,
        'todo_title', t.title,
        'status', t.status,
        'last_activity', v.last_activity_at
    )
), '[]') FROM todo_items t
LEFT JOIN v_todo_latest_journal v ON v.todo_id = t.id
WHERE date(v.last_activity_at) = '$DATE'
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
