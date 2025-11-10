#!/usr/bin/env python3
"""
CLI Viewer for lifelog-system.

Usage:
    python src/cli_viewer.py summary [--date DATE]
    python src/cli_viewer.py hourly [--date DATE]
    python src/cli_viewer.py timeline [--hours HOURS]
    python src/cli_viewer.py health [--hours HOURS]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.database.db_manager import DatabaseManager


def format_duration(seconds: int) -> str:
    """秒を時間:分:秒に変換."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def show_daily_summary(db: DatabaseManager, date: str = None) -> None:
    """日別サマリーを表示."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            process_name,
            total_seconds,
            active_seconds,
            interval_count
        FROM daily_app_usage
        WHERE date = ?
        ORDER BY total_seconds DESC
        LIMIT 20
    """,
        (date,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found for {date}")
        return

    print(f"\n=== Daily Summary for {date} ===\n")
    print(f"{'Process':<30} {'Total Time':<12} {'Active Time':<12} {'Count':<8}")
    print("-" * 70)

    total_seconds = 0
    total_active = 0

    for row in rows:
        process = row[0][:28]
        total = row[1]
        active = row[2]
        count = row[3]

        total_seconds += total
        total_active += active

        print(
            f"{process:<30} {format_duration(total):<12} {format_duration(active):<12} {count:<8}"
        )

    print("-" * 70)
    print(
        f"{'TOTAL':<30} {format_duration(total_seconds):<12} {format_duration(total_active):<12}"
    )


def show_hourly_activity(db: DatabaseManager, date: str = None) -> None:
    """時間帯別の活動状況を表示."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            strftime('%H', hour) as hour,
            active_seconds,
            idle_seconds
        FROM hourly_activity
        WHERE date(hour) = ?
        ORDER BY hour
    """,
        (date,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found for {date}")
        return

    print(f"\n=== Hourly Activity for {date} ===\n")
    print(f"{'Hour':<8} {'Active':<12} {'Idle':<12} {'Total':<12}")
    print("-" * 50)

    for row in rows:
        hour = row[0]
        active = int(row[1])
        idle = int(row[2])
        total = active + idle

        print(
            f"{hour}:00   {format_duration(active):<12} {format_duration(idle):<12} {format_duration(total):<12}"
        )


def show_timeline(db: DatabaseManager, hours: int = 2) -> None:
    """最近のタイムラインを表示."""
    start_time = datetime.now() - timedelta(hours=hours)

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            i.start_ts,
            i.end_ts,
            a.process_name,
            i.domain,
            i.is_idle,
            i.duration_seconds
        FROM activity_intervals i
        JOIN apps a ON i.app_id = a.app_id
        WHERE i.start_ts >= ?
        ORDER BY i.start_ts DESC
        LIMIT 50
    """,
        (start_time,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo data found in the last {hours} hours")
        return

    print(f"\n=== Activity Timeline (Last {hours} hours) ===\n")
    print(f"{'Time':<20} {'Duration':<12} {'Process':<25} {'Status':<10}")
    print("-" * 75)

    for row in rows:
        start_ts = row[0]
        process = row[2][:23]
        domain = row[3]
        is_idle = row[4]
        duration = row[5]

        status = "IDLE" if is_idle else "ACTIVE"
        if domain:
            process += f" ({domain})"

        print(f"{start_ts:<20} {format_duration(duration):<12} {process:<25} {status:<10}")


def show_health_metrics(db: DatabaseManager, hours: int = 24) -> None:
    """ヘルスメトリクスを表示."""
    start_time = datetime.now() - timedelta(hours=hours)

    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ts,
            cpu_percent,
            mem_mb,
            queue_depth,
            collection_delay_p95,
            dropped_events,
            db_write_time_p95
        FROM health_snapshots
        WHERE ts >= ?
        ORDER BY ts DESC
        LIMIT 20
    """,
        (start_time,),
    )

    rows = cursor.fetchall()

    if not rows:
        print(f"\nNo health data found in the last {hours} hours")
        return

    print(f"\n=== Health Metrics (Last {hours} hours) ===\n")
    print(
        f"{'Time':<20} {'CPU%':<8} {'Mem(MB)':<10} {'Queue':<8} {'Delay(s)':<10} {'Drops':<8}"
    )
    print("-" * 75)

    for row in rows:
        ts = row[0]
        cpu = row[1]
        mem = row[2]
        queue = row[3]
        delay = row[4]
        drops = row[5]

        print(
            f"{ts:<20} {cpu:<8.1f} {mem:<10.1f} {queue:<8} {delay:<10.2f} {drops:<8}"
        )

    # 最新のメトリクス
    if rows:
        latest = rows[0]
        print("\n=== Latest Status ===")
        print(f"CPU Usage: {latest[1]:.1f}%")
        print(f"Memory: {latest[2]:.1f} MB")
        print(f"Collection Delay P95: {latest[4]:.2f}s")
        print(f"Dropped Events: {latest[5]}")


def main() -> None:
    """メインエントリーポイント."""
    parser = argparse.ArgumentParser(description="Lifelog CLI Viewer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # summary コマンド
    summary_parser = subparsers.add_parser("summary", help="Show daily summary")
    summary_parser.add_argument(
        "--date", type=str, help="Date (YYYY-MM-DD, default: today)"
    )

    # hourly コマンド
    hourly_parser = subparsers.add_parser("hourly", help="Show hourly activity")
    hourly_parser.add_argument(
        "--date", type=str, help="Date (YYYY-MM-DD, default: today)"
    )

    # timeline コマンド
    timeline_parser = subparsers.add_parser("timeline", help="Show recent timeline")
    timeline_parser.add_argument(
        "--hours", type=int, default=2, help="Hours to look back (default: 2)"
    )

    # health コマンド
    health_parser = subparsers.add_parser("health", help="Show health metrics")
    health_parser.add_argument(
        "--hours", type=int, default=24, help="Hours to look back (default: 24)"
    )

    args = parser.parse_args()

    # データベース接続
    db_path = "lifelog.db"
    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Please run the collector first to generate data.")
        sys.exit(1)

    db = DatabaseManager(db_path)

    # コマンド実行
    if args.command == "summary":
        show_daily_summary(db, args.date)
    elif args.command == "hourly":
        show_hourly_activity(db, args.date)
    elif args.command == "timeline":
        show_timeline(db, args.hours)
    elif args.command == "health":
        show_health_metrics(db, args.hours)


if __name__ == "__main__":
    main()
