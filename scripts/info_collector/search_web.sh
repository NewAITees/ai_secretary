#!/usr/bin/env bash
# Web検索実行スクリプト（DuckDuckGo）
# 使い方: ./scripts/info_collector/search_web.sh "検索クエリ" [limit]

set -euo pipefail

QUERY="${1:-}"
LIMIT="${2:-10}"

if [[ -z "$QUERY" ]]; then
    echo '{"error": "検索クエリが指定されていません"}' >&2
    exit 1
fi

cd "$(dirname "$0")/../.." || exit 1

# 環境変数経由で安全にパラメータを渡す
export INFO_QUERY="$QUERY"
export INFO_LIMIT="$LIMIT"

uv run python - <<'PYTHON'
import os
import json
from src.info_collector import SearchCollector, InfoCollectorRepository

query = os.environ.get("INFO_QUERY", "")
limit = int(os.environ.get("INFO_LIMIT", "10"))

if not query:
    print(json.dumps({"error": "検索クエリが指定されていません"}, ensure_ascii=False))
    exit(1)

collector = SearchCollector()
repo = InfoCollectorRepository()

# 検索実行
results = collector.search(query, limit=limit)

# DB保存
saved_count = 0
for result in results:
    if repo.add_info(result):
        saved_count += 1

# 結果出力
output = {
    "query": query,
    "total_results": len(results),
    "saved_count": saved_count,
    "results": [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet
        }
        for r in results
    ]
}
print(json.dumps(output, ensure_ascii=False, indent=2))
PYTHON
