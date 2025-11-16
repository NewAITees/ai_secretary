#!/usr/bin/env bash
# 情報要約生成スクリプト
# 使い方: ./scripts/info_collector/generate_summary.sh [--source-type TYPE] [--query QUERY] [--no-llm] [--limit N]

set -euo pipefail

cd "$(dirname "$0")/../.." || exit 1

SOURCE_TYPE=""
QUERY=""
USE_LLM="True"
LIMIT=20

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-type)
            SOURCE_TYPE="$2"
            shift 2
            ;;
        --query)
            QUERY="$2"
            shift 2
            ;;
        --no-llm)
            USE_LLM="False"
            shift
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        *)
            echo "不明なオプション: $1" >&2
            exit 1
            ;;
    esac
done

# 環境変数経由で安全にパラメータを渡す
export INFO_QUERY="$QUERY"
export INFO_SOURCE_TYPE="$SOURCE_TYPE"
export INFO_USE_LLM="$USE_LLM"
export INFO_LIMIT="$LIMIT"

uv run python - <<'PYTHON'
import os
import json
from src.info_collector.summarizer import InfoSummarizer

query = os.environ.get("INFO_QUERY", "")
source_type = os.environ.get("INFO_SOURCE_TYPE", "")
use_llm = os.environ.get("INFO_USE_LLM", "True") == "True"
limit = int(os.environ.get("INFO_LIMIT", "20"))

summarizer = InfoSummarizer()

if query:
    # クエリ検索による要約
    result = summarizer.summarize_by_query(query, limit=limit, use_llm=use_llm)
elif source_type:
    # ソースタイプ別要約
    result = summarizer.summarize_recent(source_type=source_type, limit=limit, use_llm=use_llm)
else:
    # 全体要約
    result = summarizer.summarize_recent(limit=limit, use_llm=use_llm)

print(json.dumps(result, ensure_ascii=False, indent=2))
PYTHON
