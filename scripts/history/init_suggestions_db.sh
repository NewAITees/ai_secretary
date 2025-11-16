#!/bin/bash
#
# init_suggestions_db.sh - suggestionsテーブル作成スクリプト
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"

# DBディレクトリ作成
mkdir -p "$(dirname "$DB_PATH")"

# テーブル作成
sqlite3 "$DB_PATH" <<'EOF'
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    source_ids TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT,
    relevance_score REAL,
    presented_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback INTEGER DEFAULT 0,
    dismissed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suggestions_hash ON suggestions(hash);
CREATE INDEX IF NOT EXISTS idx_suggestions_presented_at ON suggestions(presented_at);
CREATE INDEX IF NOT EXISTS idx_suggestions_feedback ON suggestions(feedback);
EOF

echo "suggestions table created successfully"
