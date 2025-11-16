#!/bin/bash
#
# cleanup_db.sh - DB削除/アーカイブスクリプト
#
# Usage:
#   ./cleanup_db.sh --table TABLE --date-column COLUMN --days N [--archive] [--dry-run]
#
# Options:
#   --table TABLE        : テーブル名（例: collected_info）
#   --date-column COLUMN : 日付カラム名（例: fetched_at）
#   --days N            : N日以前のレコードを対象
#   --archive           : 削除前にアーカイブ（data/archive/）
#   --dry-run           : 実際の削除は行わず、対象レコード数のみ表示
#

set -euo pipefail

# デフォルト値
TABLE=""
DATE_COLUMN=""
DAYS=""
ARCHIVE=0
DRY_RUN=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ARCHIVE_DIR="$PROJECT_ROOT/data/archive"
DB_PATH="$PROJECT_ROOT/data/ai_secretary.db"

# 引数解析
while [[ $# -gt 0 ]]; do
  case $1 in
    --table)
      TABLE="$2"
      shift 2
      ;;
    --date-column)
      DATE_COLUMN="$2"
      shift 2
      ;;
    --days)
      DAYS="$2"
      shift 2
      ;;
    --archive)
      ARCHIVE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# 必須パラメータチェック
if [[ -z "$TABLE" ]] || [[ -z "$DATE_COLUMN" ]] || [[ -z "$DAYS" ]]; then
  echo "Error: --table, --date-column, and --days are required" >&2
  echo "Usage: $0 --table TABLE --date-column COLUMN --days N [--archive] [--dry-run]" >&2
  exit 1
fi

# 数値チェック
if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
  echo "Error: --days must be a positive integer" >&2
  exit 1
fi

# テーブル名のバリデーション（SQLインジェクション対策）
if ! [[ "$TABLE" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
  echo "Error: Invalid table name: $TABLE" >&2
  exit 1
fi

# カラム名のバリデーション
if ! [[ "$DATE_COLUMN" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
  echo "Error: Invalid column name: $DATE_COLUMN" >&2
  exit 1
fi

# DBファイル存在チェック
if [[ ! -f "$DB_PATH" ]]; then
  echo "Error: Database not found: $DB_PATH" >&2
  exit 1
fi

# カウンター
DB_ROWS_DELETED=0
FILES_ARCHIVED=0
STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# アーカイブディレクトリ作成
if [[ $ARCHIVE -eq 1 ]]; then
  ARCHIVE_DATE=$(date +%Y-%m-%d)
  ARCHIVE_TARGET_DIR="$ARCHIVE_DIR/$ARCHIVE_DATE"
  mkdir -p "$ARCHIVE_TARGET_DIR"
  ARCHIVE_FILE="$ARCHIVE_TARGET_DIR/${TABLE}_deleted.jsonl.gz"
fi

# 削除対象日時計算（N日前）
CUTOFF_DATE=$(date -u -d "$DAYS days ago" +"%Y-%m-%d %H:%M:%S")

# 対象レコード数取得
# is_protected カラムがある場合は除外
HAS_PROTECTED_COLUMN=$(sqlite3 "$DB_PATH" "PRAGMA table_info($TABLE);" | grep -c "is_protected" || echo "0")

if [[ $HAS_PROTECTED_COLUMN -gt 0 ]]; then
  COUNT_QUERY="SELECT COUNT(*) FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE') AND (is_protected IS NULL OR is_protected = 0);"
else
  COUNT_QUERY="SELECT COUNT(*) FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE');"
fi

TARGET_COUNT=$(sqlite3 "$DB_PATH" "$COUNT_QUERY")

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY RUN] Table: $TABLE, Date column: $DATE_COLUMN, Days: $DAYS"
  echo "[DRY RUN] Target records: $TARGET_COUNT"
  exit 0
fi

if [[ $TARGET_COUNT -eq 0 ]]; then
  echo "No records to delete"
  exit 0
fi

# アーカイブ処理（JSON Lines形式）
if [[ $ARCHIVE -eq 1 ]]; then
  if [[ $HAS_PROTECTED_COLUMN -gt 0 ]]; then
    EXPORT_QUERY="SELECT json_object(
      $(sqlite3 "$DB_PATH" "PRAGMA table_info($TABLE);" | awk -F'|' '{printf "\"%s\", %s, ", $2, $2}' | sed 's/, $//')
    ) FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE') AND (is_protected IS NULL OR is_protected = 0);"
  else
    EXPORT_QUERY="SELECT json_object(
      $(sqlite3 "$DB_PATH" "PRAGMA table_info($TABLE);" | awk -F'|' '{printf "\"%s\", %s, ", $2, $2}' | sed 's/, $//')
    ) FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE');"
  fi

  sqlite3 "$DB_PATH" "$EXPORT_QUERY" | gzip > "$ARCHIVE_FILE"
  FILES_ARCHIVED=1
fi

# レコード削除
if [[ $HAS_PROTECTED_COLUMN -gt 0 ]]; then
  DELETE_QUERY="DELETE FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE') AND (is_protected IS NULL OR is_protected = 0);"
else
  DELETE_QUERY="DELETE FROM $TABLE WHERE $DATE_COLUMN < datetime('$CUTOFF_DATE');"
fi

sqlite3 "$DB_PATH" "$DELETE_QUERY"
DB_ROWS_DELETED=$(sqlite3 "$DB_PATH" "SELECT changes();")

FINISHED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 監査ログDB記録
sqlite3 "$DB_PATH" <<EOF
INSERT INTO cleanup_jobs (
  job_name, started_at, finished_at, exit_code,
  files_processed, files_deleted, files_archived,
  db_rows_deleted, error_message, dry_run
) VALUES (
  'cleanup_db_${TABLE}',
  '$STARTED_AT',
  '$FINISHED_AT',
  0,
  0,
  0,
  $FILES_ARCHIVED,
  $DB_ROWS_DELETED,
  NULL,
  0
);
EOF

# 結果出力
echo "Database cleanup completed:"
echo "  Table: $TABLE"
echo "  Rows deleted: $DB_ROWS_DELETED"
echo "  Files archived: $FILES_ARCHIVED"

exit 0
