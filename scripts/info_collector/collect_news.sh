#!/usr/bin/env bash
# ニュース収集スクリプト
# 使い方: ./scripts/info_collector/collect_news.sh [--site-url URL | --all] [--limit N]

set -euo pipefail

cd "$(dirname "$0")/../.." || exit 1

SITE_URL=""
COLLECT_ALL=false
LIMIT=10

while [[ $# -gt 0 ]]; do
    case "$1" in
        --site-url)
            SITE_URL="$2"
            shift 2
            ;;
        --all)
            COLLECT_ALL=true
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
export INFO_COLLECT_ALL="$COLLECT_ALL"
export INFO_SITE_URL="$SITE_URL"
export INFO_LIMIT="$LIMIT"

uv run python - <<'PYTHON'
import os
import json
from src.info_collector import NewsCollector, InfoCollectorRepository, InfoCollectorConfig

collect_all = os.environ.get("INFO_COLLECT_ALL", "false") == "true"
site_url = os.environ.get("INFO_SITE_URL", "")
limit = int(os.environ.get("INFO_LIMIT", "10"))

collector = NewsCollector()
repo = InfoCollectorRepository()

if collect_all:
    # 設定ファイルから全ニュースサイトを収集
    config = InfoCollectorConfig()
    site_urls = config.load_news_sites()
    if not site_urls:
        print(json.dumps({"error": "ニュースサイトURLが設定されていません"}, ensure_ascii=False))
        exit(1)

    all_articles = collector.collect_multiple(site_urls, max_articles_per_site=limit)

    saved_count = 0
    for article in all_articles:
        if repo.add_info(article):
            saved_count += 1

    output = {
        "total_sites": len(site_urls),
        "total_articles": len(all_articles),
        "saved_count": saved_count,
        "sites": site_urls
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

elif site_url:
    # 単一ニュースサイトを収集
    articles = collector.collect(site_url, max_articles=limit)

    saved_count = 0
    for article in articles:
        if repo.add_info(article):
            saved_count += 1

    output = {
        "site_url": site_url,
        "total_articles": len(articles),
        "saved_count": saved_count,
        "articles": [
            {
                "title": a.title,
                "url": a.url,
                "snippet": a.snippet[:100] if a.snippet else None
            }
            for a in articles[:5]
        ]
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

else:
    print(json.dumps({"error": "--site-url または --all を指定してください"}, ensure_ascii=False))
    exit(1)
PYTHON
