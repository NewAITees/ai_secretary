#!/bin/bash
#
# generate_suggestions.sh - 提案生成スクリプト
#
# Usage:
#   ./generate_suggestions.sh [--limit N] [--days D]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"
OLLAMA_API="http://localhost:11434/api/generate"
MODEL="llama3.1:8b"

# デフォルト値
LIMIT=10
DAYS=7

# 引数解析
while [[ $# -gt 0 ]]; do
  case $1 in
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

# 1. 統合履歴取得
echo "Fetching recent history..." >&2
HISTORY_JSON=$("$SCRIPT_DIR/get_recent_history.sh" --type all --limit "$LIMIT" --days "$DAYS")

# 履歴が空の場合は終了
if [[ $(echo "$HISTORY_JSON" | jq 'length') -eq 0 ]]; then
  echo "No recent history found" >&2
  echo "[]"
  exit 0
fi

# 2. プロンプト読み込み
PROMPT_FILE="$PROJECT_ROOT/config/prompts/suggestion_generate.txt"
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Error: Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

PROMPT_TEMPLATE=$(cat "$PROMPT_FILE")

# 3. LLMによる提案生成
echo "Generating suggestions with LLM..." >&2

# プロンプト構築
FULL_PROMPT=$(cat <<EOF
$PROMPT_TEMPLATE

## ユーザの活動履歴

$HISTORY_JSON

## タスク

上記の活動履歴を分析し、ユーザにとって有用な提案を生成してください。
提案は最大3件まで。JSON配列で出力してください。
EOF
)

# Ollama API呼び出し
OLLAMA_RESPONSE=$(curl -s "$OLLAMA_API" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": $(echo "$FULL_PROMPT" | jq -Rs .),
    \"stream\": false,
    \"options\": {
      \"temperature\": 0.7
    }
  }")

# レスポンス解析
LLM_OUTPUT=$(echo "$OLLAMA_RESPONSE" | jq -r '.response')

# JSON抽出（```json ... ```の中身）
SUGGESTIONS_JSON=$(echo "$LLM_OUTPUT" | sed -n '/```json/,/```/p' | sed '1d;$d' || echo "[]")

# JSON妥当性チェック
if ! echo "$SUGGESTIONS_JSON" | jq empty 2>/dev/null; then
  echo "Error: Invalid JSON from LLM" >&2
  echo "$LLM_OUTPUT" >&2
  echo "[]"
  exit 1
fi

# 4. 重複チェック＆DB保存
echo "Checking for duplicates and saving..." >&2

SUGGESTION_COUNT=$(echo "$SUGGESTIONS_JSON" | jq 'length')
SAVED_COUNT=0

for ((i=0; i<SUGGESTION_COUNT; i++)); do
  SUGGESTION=$(echo "$SUGGESTIONS_JSON" | jq ".[$i]")

  TITLE=$(echo "$SUGGESTION" | jq -r '.title')
  BODY=$(echo "$SUGGESTION" | jq -r '.body')
  TAGS_JSON=$(echo "$SUGGESTION" | jq -c '.tags')
  RELEVANCE_SCORE=$(echo "$SUGGESTION" | jq -r '.relevance_score')
  SOURCES=$(echo "$SUGGESTION" | jq -c '.sources')

  # ハッシュ計算（source_ids + title + body）
  HASH=$(echo -n "$SOURCES$TITLE$BODY" | sha256sum | awk '{print $1}')

  # 重複チェック
  EXISTING=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM suggestions WHERE hash = '$HASH';")

  if [[ $EXISTING -eq 0 ]]; then
    # DB保存
    sqlite3 "$DB_PATH" <<EOF
INSERT INTO suggestions (hash, source_ids, title, body, tags_json, relevance_score)
VALUES ('$HASH', '$SOURCES', $(echo "$TITLE" | jq -Rs .), $(echo "$BODY" | jq -Rs .), '$TAGS_JSON', $RELEVANCE_SCORE);
EOF
    SAVED_COUNT=$((SAVED_COUNT + 1))
  else
    echo "Skipping duplicate suggestion: $TITLE" >&2
  fi
done

echo "Generated $SUGGESTION_COUNT suggestions, saved $SAVED_COUNT new ones" >&2

# 5. 最新の提案を返却
sqlite3 "$DB_PATH" "SELECT json_group_array(json_object(
  'id', id,
  'title', title,
  'body', body,
  'tags', json(tags_json),
  'relevance_score', relevance_score,
  'sources', json(source_ids),
  'presented_at', presented_at,
  'feedback', feedback
)) FROM (SELECT * FROM suggestions WHERE dismissed = 0 ORDER BY created_at DESC LIMIT 10);"
