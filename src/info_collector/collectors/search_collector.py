"""
DuckDuckGo検索コレクター

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - SearchResult
- src/info_collector/repository.py - データ永続化
"""

from typing import List, Optional
from datetime import datetime
from ddgs import DDGS

from ..models import SearchResult
from .base import BaseCollector


class SearchCollector(BaseCollector):
    """DuckDuckGo検索による情報収集器"""

    def __init__(self):
        self.ddgs = DDGS()

    def collect(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        DuckDuckGoで検索を実行

        Args:
            query: 検索クエリ
            max_results: 最大取得件数

        Returns:
            検索結果のリスト
        """
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            return [
                SearchResult(
                    title=result.get("title", ""),
                    url=result.get("href", ""),
                    snippet=result.get("body", ""),
                    query=query,
                    source_name="DuckDuckGo",
                    fetched_at=datetime.now(),
                )
                for result in results
            ]
        except Exception as e:
            print(f"検索エラー: {e}")
            return []

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """collectのエイリアス（互換性のため）"""
        return self.collect(query=query, max_results=limit)
