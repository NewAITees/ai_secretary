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
            echo '{"error": "Unknown option: '$1'"}' >&2
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

# SQL用のエスケープ処理
escape_sql() {
    echo "$1" | sed "s/'/''/g"
}

TITLE_ESC=$(escape_sql "$TITLE")
DETAILS_ESC=$(escape_sql "$DETAILS")
SOURCE_ESC=$(escape_sql "$SOURCE")
META_JSON_ESC=$(escape_sql "$META_JSON")

# SQL実行（エントリ挿入）
ENTRY_ID=$(sqlite3 "$DB_PATH" <<EOF
INSERT INTO journal_entries (occurred_at, title, details, source, meta_json, created_at)
VALUES ('$OCCURRED_AT', '$TITLE_ESC', $([ -n "$DETAILS" ] && echo "'$DETAILS_ESC'" || echo "NULL"), '$SOURCE_ESC', '$META_JSON_ESC', datetime('now'));
SELECT last_insert_rowid();
EOF
)

# タグ処理（カンマ区切り文字列から）
if [ -n "$TAG_NAMES" ]; then
    IFS=',' read -ra TAGS <<< "$TAG_NAMES"
    for tag_name in "${TAGS[@]}"; do
        tag_name=$(echo "$tag_name" | xargs)  # trim whitespace
        tag_name_esc=$(escape_sql "$tag_name")
        # タグ取得または作成
        TAG_ID=$(sqlite3 "$DB_PATH" <<EOF
INSERT OR IGNORE INTO journal_tags (name) VALUES ('$tag_name_esc');
SELECT id FROM journal_tags WHERE name = '$tag_name_esc';
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
        todo_id=$(echo "$todo_id" | xargs)  # trim whitespace
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
