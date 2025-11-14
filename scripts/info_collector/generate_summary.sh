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

if [[ -n "$QUERY" ]]; then
    # クエリ検索による要約
    uv run python -c "
from src.info_collector.summarizer import InfoSummarizer
import json

summarizer = InfoSummarizer()
result = summarizer.summarize_by_query('$QUERY', limit=$LIMIT, use_llm=$USE_LLM)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
elif [[ -n "$SOURCE_TYPE" ]]; then
    # ソースタイプ別要約
    uv run python -c "
from src.info_collector.summarizer import InfoSummarizer
import json

summarizer = InfoSummarizer()
result = summarizer.summarize_recent(source_type='$SOURCE_TYPE', limit=$LIMIT, use_llm=$USE_LLM)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
else
    # 全体要約
    uv run python -c "
from src.info_collector.summarizer import InfoSummarizer
import json

summarizer = InfoSummarizer()
result = summarizer.summarize_recent(limit=$LIMIT, use_llm=$USE_LLM)
print(json.dumps(result, ensure_ascii=False, indent=2))
"
fi
