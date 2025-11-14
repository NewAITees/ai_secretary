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
            echo '{"error": "Unknown option: '$1'"}' >&2
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
if [ -n "$TAG_NAME" ]; then
    TAG_NAME_ESC=$(echo "$TAG_NAME" | sed "s/'/''/g")
    JOIN_TAG="JOIN journal_entry_tags et ON et.entry_id = j.id JOIN journal_tags t ON et.tag_id = t.id AND t.name = '$TAG_NAME_ESC'"
fi

# TODOリンク検索のJOIN
JOIN_TODO=""
[ -n "$TODO_ID" ] && JOIN_TODO="JOIN journal_todo_links l ON l.entry_id = j.id AND l.todo_id = $TODO_ID"

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
            (SELECT json_group_array(t2.name)
             FROM journal_entry_tags et2
             JOIN journal_tags t2 ON et2.tag_id = t2.id
             WHERE et2.entry_id = j.id),
            '[]'
        ),
        'linked_todos', COALESCE(
            (SELECT json_group_array(json_object('todo_id', l2.todo_id, 'relation', l2.relation))
             FROM journal_todo_links l2
             WHERE l2.entry_id = j.id),
            '[]'
        )
    )
), '[]') FROM journal_entries j
$JOIN_TAG
$JOIN_TODO
WHERE $WHERE
ORDER BY j.occurred_at DESC;
EOF
