#!/bin/bash
#
# list_jobs.sh - ジョブ一覧表示スクリプト
#
# Usage:
#   ./list_jobs.sh [--verbose]
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/jobs/cleanup_jobs.json"

VERBOSE=0
if [[ "${1:-}" == "--verbose" ]]; then
  VERBOSE=1
fi

# 設定ファイル存在チェック
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

# jq存在チェック
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed" >&2
  echo "Please install it: sudo apt-get install jq" >&2
  exit 1
fi

# ジョブ一覧取得
JOBS=$(jq -r '.jobs[]' "$CONFIG_FILE")

if [[ -z "$JOBS" ]]; then
  echo "No jobs found"
  exit 0
fi

# ヘッダー出力
echo "========================================="
echo "Cleanup Jobs"
echo "========================================="
echo ""

# ジョブ数カウント
TOTAL_JOBS=$(jq -r '.jobs | length' "$CONFIG_FILE")
ENABLED_JOBS=$(jq -r '[.jobs[] | select(.enabled == true)] | length' "$CONFIG_FILE")

echo "Total jobs: $TOTAL_JOBS"
echo "Enabled jobs: $ENABLED_JOBS"
echo ""

# ジョブ詳細表示
jq -r '.jobs[] |
  "Name: \(.name)\n" +
  "Command: \(.command)\n" +
  "Args: \(.args | join(" "))\n" +
  "Schedule: \(.schedule)\n" +
  "Enabled: \(.enabled // true)\n" +
  "Dry run: \(.dry_run // false)\n" +
  "-----------------------------------------"' "$CONFIG_FILE"

# Verbose モード（次回実行時刻を計算）
if [[ $VERBOSE -eq 1 ]]; then
  echo ""
  echo "========================================="
  echo "Next Run Times (estimated)"
  echo "========================================="
  echo ""

  # croniterがインストールされているかチェック
  if uv run python -c "import croniter" 2>/dev/null; then
    jq -r '.jobs[] | select(.enabled == true) | "\(.name)|\(.schedule)"' "$CONFIG_FILE" | while IFS='|' read -r name schedule; do
      if [[ -n "$schedule" ]]; then
        NEXT_RUN=$(uv run python -c "
from croniter import croniter
from datetime import datetime
schedule = '$schedule'
now = datetime.now()
cron = croniter(schedule, now)
print(cron.get_next(datetime).strftime('%Y-%m-%d %H:%M:%S'))
")
        echo "$name: $NEXT_RUN"
      fi
    done
  else
    echo "croniter not installed, skipping next run time calculation"
  fi
fi

echo ""
