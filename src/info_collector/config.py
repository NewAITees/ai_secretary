"""
情報収集機能の設定管理

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
"""

from pathlib import Path
from typing import List


class InfoCollectorConfig:
    """情報収集の設定ローダー"""

    def __init__(self, config_dir: str = "config/info_collector"):
        self.config_dir = Path(config_dir)

    def load_rss_feeds(self) -> List[str]:
        """RSS URLリストを読み込み"""
        return self._load_urls("rss_feeds.txt")

    def load_news_sites(self) -> List[str]:
        """ニュースサイトURLリストを読み込み"""
        return self._load_urls("news_sites.txt")

    def load_search_queries(self) -> List[str]:
        """定期検索クエリリストを読み込み"""
        return self._load_lines("search_queries.txt")

    def _load_urls(self, filename: str) -> List[str]:
        """URLリストファイルを読み込み（コメント・空行をスキップ）"""
        return self._load_lines(filename)

    def _load_lines(self, filename: str) -> List[str]:
        """テキストファイルを読み込み（コメント・空行をスキップ）"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            return []

        lines = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # コメント行・空行をスキップ
                if line and not line.startswith("#"):
                    lines.append(line)
        return lines
