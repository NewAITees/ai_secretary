#!/bin/bash
# 統合DB初期化スクリプト（todo_items + journal_entries + ビュー）

set -euo pipefail

DB_PATH="${AI_SECRETARY_DB_PATH:-data/ai_secretary.db}"

# DBディレクトリ作成
mkdir -p "$(dirname "$DB_PATH")"

# 統合スキーマ作成
sqlite3 "$DB_PATH" <<'EOF'
-- ========================================
-- コンテキスト：TODO（P1 - 既存を拡張）
-- ========================================

CREATE TABLE IF NOT EXISTS todo_items (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  description   TEXT,
  status        TEXT NOT NULL CHECK (status IN ('todo','doing','done','archived')),
  priority      INTEGER NOT NULL DEFAULT 3,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  due_date      TEXT,
  tags_json     TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_todo_status ON todo_items(status);
CREATE INDEX IF NOT EXISTS idx_todo_priority ON todo_items(priority);
CREATE INDEX IF NOT EXISTS idx_todo_due ON todo_items(due_date);

CREATE TABLE IF NOT EXISTS todo_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  todo_id       INTEGER NOT NULL,
  event_type    TEXT NOT NULL,
  payload_json  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (todo_id) REFERENCES todo_items(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_todo_events_todo ON todo_events(todo_id);

-- ========================================
-- コンテキスト：ジャーナル（P2：「今日やったこと」）
-- ========================================

CREATE TABLE IF NOT EXISTS journal_entries (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at   TEXT NOT NULL,
  title         TEXT NOT NULL,
  details       TEXT,
  source        TEXT NOT NULL DEFAULT 'manual',
  meta_json     TEXT NOT NULL DEFAULT '{}',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journal_occurred ON journal_entries(occurred_at);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(date(occurred_at));

CREATE TABLE IF NOT EXISTS journal_tags (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS journal_entry_tags (
  entry_id      INTEGER NOT NULL,
  tag_id        INTEGER NOT NULL,
  PRIMARY KEY (entry_id, tag_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id)   REFERENCES journal_tags(id)    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entry_tags_entry ON journal_entry_tags(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON journal_entry_tags(tag_id);

CREATE TABLE IF NOT EXISTS journal_todo_links (
  entry_id      INTEGER NOT NULL,
  todo_id       INTEGER NOT NULL,
  relation      TEXT NOT NULL DEFAULT 'progress',
  PRIMARY KEY (entry_id, todo_id),
  FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
  FOREIGN KEY (todo_id)  REFERENCES todo_items(id)      ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_links_entry ON journal_todo_links(entry_id);
CREATE INDEX IF NOT EXISTS idx_links_todo ON journal_todo_links(todo_id);

-- ========================================
-- 横断ビュー（日次サマリー・提案機能で活用）
-- ========================================

CREATE VIEW IF NOT EXISTS v_daily_progress AS
SELECT
  date(j.occurred_at)             AS day,
  COUNT(j.id)                     AS entry_count,
  SUM(CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END) AS linked_todo_updates
FROM journal_entries j
LEFT JOIN journal_todo_links l ON l.entry_id = j.id
LEFT JOIN todo_items t         ON t.id = l.todo_id
GROUP BY date(j.occurred_at);

CREATE VIEW IF NOT EXISTS v_todo_latest_journal AS
SELECT
  t.id           AS todo_id,
  t.title        AS todo_title,
  MAX(j.occurred_at) AS last_activity_at
FROM todo_items t
LEFT JOIN journal_todo_links l ON l.todo_id = t.id
LEFT JOIN journal_entries j     ON j.id = l.entry_id
GROUP BY t.id;
EOF

echo "✓ Unified database initialized at $DB_PATH"
