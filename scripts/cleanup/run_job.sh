#!/bin/bash
#
# run_job.sh - 手動ジョブ実行スクリプト
#
# Usage:
#   ./run_job.sh JOB_NAME [--dry-run]
#
# Example:
#   ./run_job.sh cleanup_logs
#   ./run_job.sh cleanup_audio --dry-run
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/jobs/cleanup_jobs.json"

# 引数チェック
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 JOB_NAME [--dry-run]" >&2
  exit 1
fi

JOB_NAME="$1"
DRY_RUN=0

if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

# 設定ファイル存在チェック
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: Config file not found: $CONFIG_FILE" >&2
  exit 1
fi

# ジョブ検索
JOB_FOUND=0
COMMAND=""
ARGS=""

# jqでJSON解析
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed" >&2
  echo "Please install it: sudo apt-get install jq" >&2
  exit 1
fi

# ジョブ定義を取得
JOB_ENTRY=$(jq -r ".jobs[] | select(.name == \"$JOB_NAME\")" "$CONFIG_FILE")

if [[ -z "$JOB_ENTRY" ]]; then
  echo "Error: Job '$JOB_NAME' not found in $CONFIG_FILE" >&2
  exit 1
fi

# ジョブが無効化されている場合は警告
ENABLED=$(echo "$JOB_ENTRY" | jq -r '.enabled // true')
if [[ "$ENABLED" == "false" ]]; then
  echo "Warning: Job '$JOB_NAME' is disabled" >&2
fi

# コマンドと引数を取得
COMMAND=$(echo "$JOB_ENTRY" | jq -r '.command')
ARGS_JSON=$(echo "$JOB_ENTRY" | jq -r '.args // []')
ARGS=$(echo "$ARGS_JSON" | jq -r '.[]' | tr '\n' ' ')

# ドライラン指定がある場合は引数に追加
if [[ $DRY_RUN -eq 1 ]]; then
  ARGS="$ARGS --dry-run"
fi

# コマンド実行
cd "$PROJECT_ROOT"

echo "Running job: $JOB_NAME"
echo "Command: $COMMAND $ARGS"
echo ""

# コマンド実行（プロジェクトルートから）
bash -c "$COMMAND $ARGS"

exit $?
