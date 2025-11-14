"""
情報収集機能のデータモデル定義

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/repository.py - データ永続化
- src/info_collector/collectors/ - 各種データ収集器
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class CollectedInfo(BaseModel):
    """収集された情報の統合モデル"""

    id: Optional[int] = None
    source_type: str = Field(..., description="情報ソースタイプ: 'search', 'rss', 'news'")
    title: str = Field(..., description="記事タイトル")
    url: str = Field(..., description="記事URL")
    content: Optional[str] = Field(None, description="記事本文（取得可能な場合）")
    snippet: Optional[str] = Field(None, description="要約・抜粋")
    published_at: Optional[datetime] = Field(None, description="公開日時")
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="取得日時"
    )
    source_name: Optional[str] = Field(None, description="ソース名（フィード名、サイト名等）")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="その他メタデータ"
    )

    class Config:
        from_attributes = True


class SearchResult(CollectedInfo):
    """検索結果の特化モデル"""

    source_type: Literal["search"] = Field(default="search")
    query: Optional[str] = Field(None, description="検索クエリ")


class RSSEntry(CollectedInfo):
    """RSSエントリの特化モデル"""

    source_type: Literal["rss"] = Field(default="rss")
    feed_url: Optional[str] = Field(None, description="RSSフィードURL")
    author: Optional[str] = Field(None, description="著者名")


class NewsArticle(CollectedInfo):
    """ニュース記事の特化モデル"""

    source_type: Literal["news"] = Field(default="news")
    category: Optional[str] = Field(None, description="カテゴリ")
    image_url: Optional[str] = Field(None, description="アイキャッチ画像URL")


class InfoSummary(BaseModel):
    """情報要約モデル"""

    id: Optional[int] = None
    summary_type: str = Field(..., description="要約タイプ: 'daily', 'topic', 'search'")
    title: str = Field(..., description="要約タイトル")
    summary_text: str = Field(..., description="LLM生成要約本文")
    source_info_ids: list[int] = Field(
        default_factory=list, description="参照元collected_info.id"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="作成日時")
    query: Optional[str] = Field(None, description="検索クエリ（該当する場合）")

    class Config:
        from_attributes = True
