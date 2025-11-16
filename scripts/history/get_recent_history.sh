#!/bin/bash
#
# get_recent_history.sh - 統合履歴取得スクリプト
#
# Usage:
#   ./get_recent_history.sh --type TYPE [--limit N] [--days D]
#
# Options:
#   --type TYPE    : データソース（web|todo|journal|info|chat|all）
#   --limit N      : 取得件数上限（デフォルト: 50）
#   --days D       : 取得期間（デフォルト: 7日）
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"

# デフォルト値
TYPE="all"
LIMIT=50
DAYS=7

# 引数解析
while [[ $# -gt 0 ]]; do
  case $1 in
    --type)
      TYPE="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --days)
      DAYS="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# 型チェック
if [[ ! "$TYPE" =~ ^(web|todo|journal|info|chat|all)$ ]]; then
  echo "Error: --type must be one of: web, todo, journal, info, chat, all" >&2
  exit 1
fi

# DB存在チェック
if [[ ! -f "$DB_PATH" ]]; then
  echo "Error: Database not found: $DB_PATH" >&2
  exit 1
fi

# 期間計算
CUTOFF_DATE=$(date -u -d "$DAYS days ago" +"%Y-%m-%d %H:%M:%S")

# JSON出力開始
echo "["

FIRST_ITEM=1

# browser_history取得
if [[ "$TYPE" == "web" ]] || [[ "$TYPE" == "all" ]]; then
  # browser_historyテーブルが存在するかチェック
  if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='browser_history';" | grep -q "browser_history"; then
    while IFS='|' read -r id title url visited_at; do
      if [[ $FIRST_ITEM -eq 0 ]]; then
        echo ","
      fi
      FIRST_ITEM=0

      # JSON出力（エスケープ処理）
      TITLE_ESC=$(echo "$title" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')
      URL_ESC=$(echo "$url" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')

      cat <<EOF
  {
    "source": "browser_history",
    "title": "$TITLE_ESC",
    "body": "$URL_ESC",
    "tags": ["web"],
    "timestamp": "$visited_at",
    "relevance_score": 0.5
  }
EOF
    done < <(sqlite3 "$DB_PATH" "SELECT id, title, url, visited_at FROM browser_history WHERE visited_at > datetime('$CUTOFF_DATE') ORDER BY visited_at DESC LIMIT $LIMIT;" | head -n "$LIMIT")
  fi
fi

# todo_items取得
if [[ "$TYPE" == "todo" ]] || [[ "$TYPE" == "all" ]]; then
  # todo_itemsテーブルが存在するかチェック
  if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='todo_items';" | grep -q "todo_items"; then
    while IFS='|' read -r id title description due_date status created_at; do
      if [[ $FIRST_ITEM -eq 0 ]]; then
        echo ","
      fi
      FIRST_ITEM=0

      # JSON出力（エスケープ処理）
      TITLE_ESC=$(echo "$title" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')
      DESC_ESC=$(echo "${description:-}" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')

      # relevance_score計算（締切近い・未完了はスコア高）
      SCORE=0.5
      if [[ "$status" != "done" ]]; then
        SCORE=0.7
        if [[ -n "$due_date" ]]; then
          SCORE=0.9
        fi
      fi

      cat <<EOF
  {
    "source": "todo_items",
    "title": "$TITLE_ESC",
    "body": "$DESC_ESC",
    "tags": ["todo", "$status"],
    "timestamp": "$created_at",
    "relevance_score": $SCORE
  }
EOF
    done < <(sqlite3 "$DB_PATH" "SELECT id, title, description, due_date, status, created_at FROM todo_items WHERE created_at > datetime('$CUTOFF_DATE') ORDER BY created_at DESC LIMIT $LIMIT;" | head -n "$LIMIT")
  fi
fi

# journal_entries取得
if [[ "$TYPE" == "journal" ]] || [[ "$TYPE" == "all" ]]; then
  # journal_entriesテーブルが存在するかチェック
  if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='journal_entries';" | grep -q "journal_entries"; then
    while IFS='|' read -r id title content created_at; do
      if [[ $FIRST_ITEM -eq 0 ]]; then
        echo ","
      fi
      FIRST_ITEM=0

      # JSON出力（エスケープ処理）
      TITLE_ESC=$(echo "$title" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')
      CONTENT_ESC=$(echo "${content:-}" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')

      cat <<EOF
  {
    "source": "journal_entries",
    "title": "$TITLE_ESC",
    "body": "$CONTENT_ESC",
    "tags": ["journal"],
    "timestamp": "$created_at",
    "relevance_score": 0.6
  }
EOF
    done < <(sqlite3 "$DB_PATH" "SELECT id, title, content, created_at FROM journal_entries WHERE created_at > datetime('$CUTOFF_DATE') ORDER BY created_at DESC LIMIT $LIMIT;" | head -n "$LIMIT")
  fi
fi

# collected_info取得
if [[ "$TYPE" == "info" ]] || [[ "$TYPE" == "all" ]]; then
  # collected_infoテーブルが存在するかチェック
  if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='collected_info';" | grep -q "collected_info"; then
    while IFS='|' read -r id title url fetched_at; do
      if [[ $FIRST_ITEM -eq 0 ]]; then
        echo ","
      fi
      FIRST_ITEM=0

      # JSON出力（エスケープ処理）
      TITLE_ESC=$(echo "$title" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')
      URL_ESC=$(echo "${url:-}" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')

      cat <<EOF
  {
    "source": "collected_info",
    "title": "$TITLE_ESC",
    "body": "$URL_ESC",
    "tags": ["info"],
    "timestamp": "$fetched_at",
    "relevance_score": 0.55
  }
EOF
    done < <(sqlite3 "$DB_PATH" "SELECT id, title, url, fetched_at FROM collected_info WHERE fetched_at > datetime('$CUTOFF_DATE') ORDER BY fetched_at DESC LIMIT $LIMIT;" | head -n "$LIMIT")
  fi
fi

# chat_history取得
if [[ "$TYPE" == "chat" ]] || [[ "$TYPE" == "all" ]]; then
  # chat_historyテーブルが存在するかチェック
  if sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history';" | grep -q "chat_history"; then
    while IFS='|' read -r id role content created_at; do
      if [[ $FIRST_ITEM -eq 0 ]]; then
        echo ","
      fi
      FIRST_ITEM=0

      # JSON出力（エスケープ処理）
      CONTENT_ESC=$(echo "$content" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read().strip()))" | sed 's/^"//;s/"$//')

      cat <<EOF
  {
    "source": "chat_history",
    "title": "Chat ($role)",
    "body": "$CONTENT_ESC",
    "tags": ["chat", "$role"],
    "timestamp": "$created_at",
    "relevance_score": 0.4
  }
EOF
    done < <(sqlite3 "$DB_PATH" "SELECT id, role, content, created_at FROM chat_history WHERE created_at > datetime('$CUTOFF_DATE') ORDER BY created_at DESC LIMIT $LIMIT;" | head -n "$LIMIT")
  fi
fi

# JSON出力終了
echo ""
echo "]"
