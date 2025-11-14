#!/usr/bin/env bash
# RSS収集スクリプト
# 使い方: ./scripts/info_collector/collect_rss.sh [--feed-url URL | --all] [--limit N]

set -euo pipefail

cd "$(dirname "$0")/../.." || exit 1

FEED_URL=""
COLLECT_ALL=false
LIMIT=20

while [[ $# -gt 0 ]]; do
    case "$1" in
        --feed-url)
            FEED_URL="$2"
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
    # 設定ファイルから全RSSを収集
    uv run python -c "
from src.info_collector import RSSCollector, InfoCollectorRepository, InfoCollectorConfig
import json

config = InfoCollectorConfig()
collector = RSSCollector()
repo = InfoCollectorRepository()

feed_urls = config.load_rss_feeds()
if not feed_urls:
    print(json.dumps({'error': 'RSS URLが設定されていません'}, ensure_ascii=False))
    exit(1)

all_entries = collector.collect_multiple(feed_urls, max_entries_per_feed=$LIMIT)

saved_count = 0
for entry in all_entries:
    if repo.add_info(entry):
        saved_count += 1

output = {
    'total_feeds': len(feed_urls),
    'total_entries': len(all_entries),
    'saved_count': saved_count,
    'feeds': feed_urls
}
print(json.dumps(output, ensure_ascii=False, indent=2))
"
elif [[ -n "$FEED_URL" ]]; then
    # 単一RSSを収集
    uv run python -c "
from src.info_collector import RSSCollector, InfoCollectorRepository
import json

collector = RSSCollector()
repo = InfoCollectorRepository()

entries = collector.collect('$FEED_URL', max_entries=$LIMIT)

saved_count = 0
for entry in entries:
    if repo.add_info(entry):
        saved_count += 1

output = {
    'feed_url': '$FEED_URL',
    'total_entries': len(entries),
    'saved_count': saved_count,
    'entries': [
        {
            'title': e.title,
            'url': e.url,
            'published_at': e.published_at.isoformat() if e.published_at else None
        }
        for e in entries[:5]
    ]
}
print(json.dumps(output, ensure_ascii=False, indent=2))
"
else
    echo "使い方: $0 [--feed-url URL | --all] [--limit N]" >&2
    exit 1
fi
