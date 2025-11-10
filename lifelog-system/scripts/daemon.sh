#!/bin/bash
# Lifelog System Daemon Control Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/lifelog.pid"
LOG_FILE="$PROJECT_DIR/logs/lifelog_daemon.log"

# ログディレクトリ作成
mkdir -p "$PROJECT_DIR/logs"

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Lifelog is already running (PID: $PID)"
            return 1
        fi
    fi

    echo "Starting lifelog daemon..."
    cd "$PROJECT_DIR"
    nohup uv run python -m src.main_collector > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Lifelog started (PID: $(cat $PID_FILE))"
    echo "Log file: $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Lifelog is not running"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping lifelog (PID: $PID)..."
        kill "$PID"

        # 最大10秒待つ
        for i in {1..10}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        # まだ動いている場合は強制終了
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force killing lifelog..."
            kill -9 "$PID"
        fi

        rm -f "$PID_FILE"
        echo "Lifelog stopped"
    else
        echo "Lifelog is not running (stale PID file)"
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Lifelog is not running"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Lifelog is running (PID: $PID)"

        # メモリ使用量表示
        MEM=$(ps -p "$PID" -o rss= | awk '{print $1/1024 " MB"}')
        echo "Memory usage: $MEM"

        # ログファイルの最終行
        if [ -f "$LOG_FILE" ]; then
            echo "Last log entry:"
            tail -n 1 "$LOG_FILE"
        fi

        return 0
    else
        echo "Lifelog is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

restart() {
    stop
    sleep 2
    start
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "Log file not found: $LOG_FILE"
        return 1
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
