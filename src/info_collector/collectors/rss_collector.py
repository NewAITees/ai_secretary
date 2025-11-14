"""
RSSフィードコレクター

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - RSSEntry
- src/info_collector/repository.py - データ永続化
"""

from typing import List
from datetime import datetime
import time
import feedparser

from ..models import RSSEntry
from .base import BaseCollector


class RSSCollector(BaseCollector):
    """RSSフィードによる情報収集器"""

    def collect(self, feed_url: str, max_entries: int = 20) -> List[RSSEntry]:
        """
        RSSフィードからエントリを取得

        Args:
            feed_url: RSSフィードURL
            max_entries: 最大取得件数

        Returns:
            RSSエントリのリスト
        """
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get("title", "Unknown Feed")

            entries = []
            for entry in feed.entries[:max_entries]:
                # 公開日時のパース
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry.published_parsed)
                    )
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published_at = datetime.fromtimestamp(
                        time.mktime(entry.updated_parsed)
                    )

                # エントリ作成
                entries.append(
                    RSSEntry(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        snippet=entry.get("summary", ""),
                        content=entry.get("content", [{}])[0].get("value")
                        if entry.get("content")
                        else None,
                        published_at=published_at,
                        source_name=feed_title,
                        feed_url=feed_url,
                        author=entry.get("author"),
                        fetched_at=datetime.now(),
                    )
                )

            return entries
        except Exception as e:
            print(f"RSS取得エラー ({feed_url}): {e}")
            return []

    def collect_multiple(
        self, feed_urls: List[str], max_entries_per_feed: int = 20
    ) -> List[RSSEntry]:
        """
        複数のRSSフィードから一括取得

        Args:
            feed_urls: RSSフィードURLのリスト
            max_entries_per_feed: フィードあたりの最大取得件数

        Returns:
            全フィードのエントリリスト
        """
        all_entries = []
        for url in feed_urls:
            entries = self.collect(url, max_entries=max_entries_per_feed)
            all_entries.extend(entries)
        return all_entries
