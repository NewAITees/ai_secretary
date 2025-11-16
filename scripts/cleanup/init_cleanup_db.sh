#!/bin/bash
#
# init_cleanup_db.sh - cleanup_jobsテーブル作成スクリプト
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"

# DBディレクトリ作成
mkdir -p "$(dirname "$DB_PATH")"

# テーブル作成
sqlite3 "$DB_PATH" <<'EOF'
CREATE TABLE IF NOT EXISTS cleanup_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    files_processed INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    files_archived INTEGER DEFAULT 0,
    db_rows_deleted INTEGER DEFAULT 0,
    error_message TEXT,
    dry_run BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_job_name ON cleanup_jobs(job_name);
CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_started_at ON cleanup_jobs(started_at);
EOF

echo "cleanup_jobs table created successfully"
