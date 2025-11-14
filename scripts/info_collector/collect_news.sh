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

if [[ "$COLLECT_ALL" == "true" ]]; then
    # 設定ファイルから全ニュースサイトを収集
    uv run python -c "
from src.info_collector import NewsCollector, InfoCollectorRepository, InfoCollectorConfig
import json

config = InfoCollectorConfig()
collector = NewsCollector()
repo = InfoCollectorRepository()

site_urls = config.load_news_sites()
if not site_urls:
    print(json.dumps({'error': 'ニュースサイトURLが設定されていません'}, ensure_ascii=False))
    exit(1)

all_articles = collector.collect_multiple(site_urls, max_articles_per_site=$LIMIT)

saved_count = 0
for article in all_articles:
    if repo.add_info(article):
        saved_count += 1

output = {
    'total_sites': len(site_urls),
    'total_articles': len(all_articles),
    'saved_count': saved_count,
    'sites': site_urls
}
print(json.dumps(output, ensure_ascii=False, indent=2))
"
elif [[ -n "$SITE_URL" ]]; then
    # 単一ニュースサイトを収集
    uv run python -c "
from src.info_collector import NewsCollector, InfoCollectorRepository
import json

collector = NewsCollector()
repo = InfoCollectorRepository()

articles = collector.collect('$SITE_URL', max_articles=$LIMIT)

saved_count = 0
for article in articles:
    if repo.add_info(article):
        saved_count += 1

output = {
    'site_url': '$SITE_URL',
    'total_articles': len(articles),
    'saved_count': saved_count,
    'articles': [
        {
            'title': a.title,
            'url': a.url,
            'snippet': a.snippet[:100] if a.snippet else None
        }
        for a in articles[:5]
    ]
}
print(json.dumps(output, ensure_ascii=False, indent=2))
"
else
    echo "使い方: $0 [--site-url URL | --all] [--limit N]" >&2
    exit 1
fi
