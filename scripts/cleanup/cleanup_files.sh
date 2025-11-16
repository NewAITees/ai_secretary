#!/bin/bash
#
# cleanup_files.sh - ファイル削除/アーカイブスクリプト
#
# Usage:
#   ./cleanup_files.sh --glob "logs/*.log" --days 14 [--archive] [--dry-run]
#
# Options:
#   --glob PATTERN     : ファイルパターン（例: "logs/*.log"）
#   --days N          : N日以前のファイルを対象
#   --archive         : 削除前にアーカイブ（data/archive/）
#   --dry-run         : 実際の削除は行わず、対象ファイルのみ表示
#

set -euo pipefail

# デフォルト値
GLOB_PATTERN=""
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
    --glob)
      GLOB_PATTERN="$2"
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
if [[ -z "$GLOB_PATTERN" ]] || [[ -z "$DAYS" ]]; then
  echo "Error: --glob and --days are required" >&2
  echo "Usage: $0 --glob PATTERN --days N [--archive] [--dry-run]" >&2
  exit 1
fi

# 数値チェック
if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
  echo "Error: --days must be a positive integer" >&2
  exit 1
fi

# プロジェクトルートに移動
cd "$PROJECT_ROOT"

# カウンター
FILES_PROCESSED=0
FILES_DELETED=0
FILES_ARCHIVED=0
STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# アーカイブディレクトリ作成
if [[ $ARCHIVE -eq 1 ]]; then
  ARCHIVE_DATE=$(date +%Y-%m-%d)
  ARCHIVE_TARGET_DIR="$ARCHIVE_DIR/$ARCHIVE_DATE"
  mkdir -p "$ARCHIVE_TARGET_DIR"
fi

# 対象ファイル検索（N日以前）
# findコマンドで-mtimeを使用
FIND_PATTERN="$GLOB_PATTERN"

# glob パターンをfind用に変換
# 例: "logs/*.log" -> "-path ./logs/*.log"
FIND_PATH_PATTERN="./$GLOB_PATTERN"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[DRY RUN] Target pattern: $GLOB_PATTERN, Days: $DAYS"
fi

# ファイル検索と処理
while IFS= read -r -d '' file; do
  FILES_PROCESSED=$((FILES_PROCESSED + 1))

  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY RUN] Would process: $file"
    continue
  fi

  # アーカイブ処理
  if [[ $ARCHIVE -eq 1 ]]; then
    # 相対パスを保持してアーカイブ
    RELATIVE_PATH="${file#./}"
    ARCHIVE_FILE="$ARCHIVE_TARGET_DIR/$RELATIVE_PATH"
    ARCHIVE_FILE_DIR="$(dirname "$ARCHIVE_FILE")"
    mkdir -p "$ARCHIVE_FILE_DIR"

    # gzip圧縮してアーカイブ
    gzip -c "$file" > "$ARCHIVE_FILE.gz"
    FILES_ARCHIVED=$((FILES_ARCHIVED + 1))
  fi

  # ファイル削除
  rm -f "$file"
  FILES_DELETED=$((FILES_DELETED + 1))
done < <(find . -type f -path "$FIND_PATH_PATTERN" -mtime +"$DAYS" -print0 2>/dev/null || true)

FINISHED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# 監査ログDB記録
if [[ $DRY_RUN -eq 0 ]]; then
  sqlite3 "$DB_PATH" <<EOF
INSERT INTO cleanup_jobs (
  job_name, started_at, finished_at, exit_code,
  files_processed, files_deleted, files_archived,
  db_rows_deleted, error_message, dry_run
) VALUES (
  'cleanup_files',
  '$STARTED_AT',
  '$FINISHED_AT',
  0,
  $FILES_PROCESSED,
  $FILES_DELETED,
  $FILES_ARCHIVED,
  0,
  NULL,
  0
);
EOF
fi

# 結果出力
echo "Cleanup completed:"
echo "  Files processed: $FILES_PROCESSED"
echo "  Files deleted: $FILES_DELETED"
echo "  Files archived: $FILES_ARCHIVED"
echo "  Dry run: $DRY_RUN"

exit 0
