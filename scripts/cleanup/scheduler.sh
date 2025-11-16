#!/bin/bash
#
# scheduler.sh - スケジューラデーモン制御スクリプト
#
# Usage:
#   ./scheduler.sh start   - スケジューラを起動
#   ./scheduler.sh stop    - スケジューラを停止
#   ./scheduler.sh status  - スケジューラの状態を確認
#   ./scheduler.sh restart - スケジューラを再起動
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PID_FILE="$PROJECT_ROOT/data/scheduler.pid"
LOG_FILE="$PROJECT_ROOT/logs/scheduler_audit.log"
SCHEDULER_SCRIPT="$SCRIPT_DIR/scheduler.py"

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# ログディレクトリ作成
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$(dirname "$PID_FILE")"

# 関数: スケジューラが実行中かチェック
is_running() {
  if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
      return 0  # 実行中
    else
      # PIDファイルは存在するがプロセスが存在しない
      rm -f "$PID_FILE"
      return 1
    fi
  else
    return 1  # 実行中ではない
  fi
}

# 関数: スケジューラを起動
start_scheduler() {
  if is_running; then
    echo -e "${YELLOW}Scheduler is already running (PID: $(cat "$PID_FILE"))${NC}"
    return 0
  fi

  echo "Starting scheduler..."

  # バックグラウンドでスケジューラを起動
  cd "$PROJECT_ROOT"
  nohup uv run python "$SCHEDULER_SCRIPT" >> "$LOG_FILE" 2>&1 &
  PID=$!

  # PIDファイル作成
  echo "$PID" > "$PID_FILE"

  # 起動確認（1秒待機）
  sleep 1

  if is_running; then
    echo -e "${GREEN}Scheduler started successfully (PID: $PID)${NC}"
  else
    echo -e "${RED}Failed to start scheduler${NC}"
    rm -f "$PID_FILE"
    return 1
  fi
}

# 関数: スケジューラを停止
stop_scheduler() {
  if ! is_running; then
    echo -e "${YELLOW}Scheduler is not running${NC}"
    return 0
  fi

  PID=$(cat "$PID_FILE")
  echo "Stopping scheduler (PID: $PID)..."

  # SIGTERM送信
  kill "$PID" 2>/dev/null || true

  # 最大10秒待機
  for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  # まだ実行中なら強制終了
  if ps -p "$PID" > /dev/null 2>&1; then
    echo "Force killing scheduler..."
    kill -9 "$PID" 2>/dev/null || true
  fi

  rm -f "$PID_FILE"
  echo -e "${GREEN}Scheduler stopped${NC}"
}

# 関数: スケジューラの状態を確認
status_scheduler() {
  if is_running; then
    PID=$(cat "$PID_FILE")
    echo -e "${GREEN}Scheduler is running (PID: $PID)${NC}"

    # プロセス情報表示
    ps -p "$PID" -o pid,ppid,cmd,etime 2>/dev/null || true
  else
    echo -e "${RED}Scheduler is not running${NC}"
  fi
}

# 関数: スケジューラを再起動
restart_scheduler() {
  stop_scheduler
  sleep 2
  start_scheduler
}

# メイン処理
case "${1:-}" in
  start)
    start_scheduler
    ;;
  stop)
    stop_scheduler
    ;;
  status)
    status_scheduler
    ;;
  restart)
    restart_scheduler
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac

exit 0
