#!/bin/bash
#
# test_tool_executor.sh - Tool Executor動作確認スクリプト
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "Tool Executor Test"
echo "========================================="
echo ""

# サーバー起動確認
echo "1. Checking if server is running..."
if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
  echo "Error: Server is not running"
  echo "Please start the server with: uv run python scripts/dev_server.py"
  exit 1
fi
echo "✓ Server is running"
echo ""

# ツール一覧取得
echo "2. Listing available tools..."
TOOLS_RESPONSE=$(curl -s http://localhost:8000/api/tools/list)
echo "$TOOLS_RESPONSE" | python3 -m json.tool
echo ""

# get_todos ツール実行（read_only、権限あり）
echo "3. Testing get_todos tool (role=assistant)..."
GET_TODOS_REQUEST='{
  "tool": "get_todos",
  "args": {"status": "all", "limit": 5},
  "role": "assistant"
}'

GET_TODOS_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d "$GET_TODOS_REQUEST")

echo "$GET_TODOS_RESPONSE" | python3 -m json.tool
echo ""

# cleanup_logs ツール実行（role=assistant、権限なし）
echo "4. Testing cleanup_logs tool (role=assistant, should fail)..."
CLEANUP_REQUEST='{
  "tool": "cleanup_logs",
  "args": {"glob": "logs/*.log", "days": 14},
  "role": "assistant"
}'

CLEANUP_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d "$CLEANUP_REQUEST")

echo "$CLEANUP_RESPONSE" | python3 -m json.tool
echo ""

# cleanup_logs ツール実行（role=admin、権限あり、ドライラン）
echo "5. Testing cleanup_logs tool (role=admin, dry-run)..."
CLEANUP_ADMIN_REQUEST='{
  "tool": "cleanup_logs",
  "args": {"glob": "logs/*.log", "days": 14, "archive": true},
  "role": "admin"
}'

# Note: このテストは実際のcleanup_files.shが必要
# 実装されていない場合はエラーになる可能性がある

# 監査ログ確認
echo "6. Checking audit logs..."
sqlite3 "$PROJECT_ROOT/data/ai_secretary.db" "SELECT tool_name, role, exit_code, elapsed_ms FROM tool_audit ORDER BY started_at DESC LIMIT 5;"
echo ""

echo "========================================="
echo "Test completed"
echo "========================================="
