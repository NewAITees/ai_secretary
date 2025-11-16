#!/bin/bash
#
# init_tool_audit_db.sh - tool_auditテーブル作成スクリプト
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"

# DBディレクトリ作成
mkdir -p "$(dirname "$DB_PATH")"

# テーブル作成
sqlite3 "$DB_PATH" <<'EOF'
CREATE TABLE IF NOT EXISTS tool_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    elapsed_ms INTEGER,
    retriable BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_session_id ON tool_audit(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_audit_tool_name ON tool_audit(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_audit_started_at ON tool_audit(started_at);
EOF

echo "tool_audit table created successfully"
