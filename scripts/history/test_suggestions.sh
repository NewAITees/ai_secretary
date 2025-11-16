#!/bin/bash
#
# test_suggestions.sh - 提案生成機能のテストスクリプト
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "Suggestions Feature Test"
echo "========================================="
echo ""

# サーバー起動確認
echo "1. Checking if server is running..."
if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
  echo "Warning: Server is not running"
  echo "Some tests will be skipped"
  echo "To run all tests, start the server with: uv run python scripts/dev_server.py"
  echo ""
fi

# 統合履歴取得テスト
echo "2. Testing get_recent_history.sh..."
HISTORY_OUTPUT=$("$SCRIPT_DIR/get_recent_history.sh" --type todo --limit 5 --days 30)
echo "$HISTORY_OUTPUT" | python3 -m json.tool | head -n 20
echo "..."
echo ""

# suggestions テーブル確認
echo "3. Checking suggestions table..."
sqlite3 "$PROJECT_ROOT/data/ai_secretary.db" "SELECT COUNT(*) as suggestion_count FROM suggestions;"
echo ""

# API エンドポイントテスト（サーバーが起動している場合のみ）
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
  echo "4. Testing GET /api/suggestions..."
  SUGGESTIONS_RESPONSE=$(curl -s http://localhost:8000/api/suggestions?limit=5)
  echo "$SUGGESTIONS_RESPONSE" | python3 -m json.tool
  echo ""

  # フィードバック設定テスト（提案が存在する場合のみ）
  SUGGESTION_COUNT=$(echo "$SUGGESTIONS_RESPONSE" | jq '.suggestions | length')
  if [[ $SUGGESTION_COUNT -gt 0 ]]; then
    FIRST_SUGGESTION_ID=$(echo "$SUGGESTIONS_RESPONSE" | jq -r '.suggestions[0].id')

    echo "5. Testing POST /api/suggestions/{id}/feedback..."
    FEEDBACK_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/suggestions/$FIRST_SUGGESTION_ID/feedback" \
      -H "Content-Type: application/json" \
      -d '{"feedback": 1}')
    echo "$FEEDBACK_RESPONSE" | python3 -m json.tool
    echo ""

    echo "6. Testing POST /api/suggestions/{id}/dismiss..."
    # 新しい提案を作成してからdismiss（既存の提案をdismissしないため）
    # ここではスキップ
    echo "Skipped (to preserve existing suggestions)"
    echo ""
  else
    echo "No suggestions found, skipping feedback tests"
    echo ""
  fi

  # Tool Executor経由でのテスト
  echo "7. Testing generate_suggestions via Tool Executor..."
  TOOL_EXECUTE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tools/execute \
    -H "Content-Type: application/json" \
    -d '{
      "tool": "generate_suggestions",
      "args": {"limit": 3, "days": 7},
      "role": "assistant"
    }')

  echo "$TOOL_EXECUTE_RESPONSE" | python3 -m json.tool | head -n 30
  echo "..."
  echo ""
else
  echo "Server not running, skipping API tests"
  echo ""
fi

# DB検証
echo "8. Verifying database state..."
sqlite3 "$PROJECT_ROOT/data/ai_secretary.db" "SELECT COUNT(*) as total, SUM(CASE WHEN dismissed = 0 THEN 1 ELSE 0 END) as active, SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive_feedback FROM suggestions;"
echo ""

echo "========================================="
echo "Test completed"
echo "========================================="
