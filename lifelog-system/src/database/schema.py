"""
SQLite database schema for lifelog-system.

Design: Interval-normalized schema with WAL mode optimization.
See: doc/design/database_design.md
"""

CREATE_TABLES_SQL = """
-- ========================================
-- apps: アプリケーションマスタ（重複除去）
-- ========================================
CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_name TEXT NOT NULL,
    process_path_hash TEXT NOT NULL,
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    UNIQUE(process_name, process_path_hash)
);

CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(process_name);

-- ========================================
-- activity_intervals: 活動区間（メインデータ）
-- ========================================
CREATE TABLE IF NOT EXISTS activity_intervals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts DATETIME NOT NULL,
    end_ts DATETIME NOT NULL,
    app_id INTEGER NOT NULL,
    window_hash TEXT NOT NULL,
    domain TEXT,
    is_idle INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER GENERATED ALWAYS AS
        (CAST((julianday(end_ts) - julianday(start_ts)) * 86400 AS INTEGER)) STORED,
    FOREIGN KEY(app_id) REFERENCES apps(app_id)
);

CREATE INDEX IF NOT EXISTS idx_intervals_time ON activity_intervals(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_intervals_app ON activity_intervals(app_id);
CREATE INDEX IF NOT EXISTS idx_intervals_date ON activity_intervals(date(start_ts));

-- ========================================
-- health_snapshots: ヘルスモニタリング（SLO計測用）
-- ========================================
CREATE TABLE IF NOT EXISTS health_snapshots (
    ts DATETIME PRIMARY KEY,
    cpu_percent REAL,
    mem_mb REAL,
    queue_depth INTEGER,
    collection_delay_p50 REAL,
    collection_delay_p95 REAL,
    dropped_events INTEGER,
    db_write_time_p95 REAL
);

CREATE INDEX IF NOT EXISTS idx_health_ts ON health_snapshots(ts);

-- ========================================
-- 集計用ビュー（クエリ高速化）
-- ========================================
CREATE VIEW IF NOT EXISTS daily_app_usage AS
SELECT
    date(start_ts) as date,
    i.app_id,
    a.process_name,
    SUM(duration_seconds) as total_seconds,
    COUNT(*) as interval_count,
    SUM(CASE WHEN is_idle = 0 THEN duration_seconds ELSE 0 END) as active_seconds
FROM activity_intervals i
JOIN apps a ON i.app_id = a.app_id
GROUP BY date(start_ts), i.app_id;

CREATE VIEW IF NOT EXISTS hourly_activity AS
SELECT
    datetime(start_ts, 'start of hour') as hour,
    SUM(CASE WHEN is_idle = 0 THEN duration_seconds ELSE 0 END) as active_seconds,
    SUM(CASE WHEN is_idle = 1 THEN duration_seconds ELSE 0 END) as idle_seconds
FROM activity_intervals
GROUP BY datetime(start_ts, 'start of hour');
"""


def get_pragma_settings() -> list[str]:
    """
    WALモード用のPRAGMA設定を取得.

    Returns:
        PRAGMA設定のSQLリスト
    """
    return [
        "PRAGMA journal_mode=WAL;",
        "PRAGMA synchronous=NORMAL;",
        "PRAGMA temp_store=MEMORY;",
        "PRAGMA mmap_size=268435456;",  # 256MB
        "PRAGMA page_size=4096;",
        "PRAGMA cache_size=-20000;",  # 約20MB
        "PRAGMA busy_timeout=5000;",  # 5秒
    ]
