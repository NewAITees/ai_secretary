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
            echo '{"error": "Unknown option: '$1'"}' >&2
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
