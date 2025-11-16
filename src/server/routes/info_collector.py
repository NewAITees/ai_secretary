"""情報収集機能のAPIルート"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from src.info_collector import (
    InfoCollectorRepository,
    SearchCollector,
    RSSCollector,
    NewsCollector,
    InfoCollectorConfig,
)
from src.info_collector.summarizer import InfoSummarizer


router = APIRouter(prefix="/api/info", tags=["info-collector"])


class SearchRequest(BaseModel):
    """検索リクエスト"""

    query: str
    limit: int = 10


class RSSCollectRequest(BaseModel):
    """RSS収集リクエスト"""

    feed_url: Optional[str] = None
    collect_all: bool = False
    limit: int = 20


class NewsCollectRequest(BaseModel):
    """ニュース収集リクエスト"""

    site_url: Optional[str] = None
    collect_all: bool = False
    limit: int = 10


class SummaryRequest(BaseModel):
    """要約生成リクエスト"""

    source_type: Optional[str] = None
    query: Optional[str] = None
    limit: int = 20
    use_llm: bool = True


@router.post("/search")
async def search_web(request: SearchRequest):
    """Web検索を実行してDBに保存"""
    def _search():
        collector = SearchCollector()
        repo = InfoCollectorRepository()

        results = collector.search(request.query, limit=request.limit)

        saved_count = 0
        for result in results:
            if repo.add_info(result):
                saved_count += 1

        return {
            "query": request.query,
            "total_results": len(results),
            "saved_count": saved_count,
            "results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet} for r in results
            ],
        }

    return await run_in_threadpool(_search)


@router.post("/rss/collect")
async def collect_rss(request: RSSCollectRequest):
    """RSSフィードを収集"""
    def _collect_rss():
        collector = RSSCollector()
        repo = InfoCollectorRepository()
        config = InfoCollectorConfig()

        if request.collect_all:
            feed_urls = config.load_rss_feeds()
            if not feed_urls:
                raise HTTPException(status_code=400, detail="RSS URLが設定されていません")

            all_entries = collector.collect_multiple(feed_urls, max_entries_per_feed=request.limit)
        elif request.feed_url:
            all_entries = collector.collect(request.feed_url, max_entries=request.limit)
        else:
            raise HTTPException(status_code=400, detail="--feed-url または --collect-all を指定してください")

        saved_count = 0
        for entry in all_entries:
            if repo.add_info(entry):
                saved_count += 1

        return {
            "total_entries": len(all_entries),
            "saved_count": saved_count,
        }

    return await run_in_threadpool(_collect_rss)


@router.post("/news/collect")
async def collect_news(request: NewsCollectRequest):
    """ニュースサイトを収集"""
    def _collect_news():
        collector = NewsCollector()
        repo = InfoCollectorRepository()
        config = InfoCollectorConfig()

        if request.collect_all:
            site_urls = config.load_news_sites()
            if not site_urls:
                raise HTTPException(status_code=400, detail="ニュースサイトURLが設定されていません")

            all_articles = collector.collect_multiple(site_urls, max_articles_per_site=request.limit)
        elif request.site_url:
            all_articles = collector.collect(request.site_url, max_articles=request.limit)
        else:
            raise HTTPException(status_code=400, detail="--site-url または --collect-all を指定してください")

        saved_count = 0
        for article in all_articles:
            if repo.add_info(article):
                saved_count += 1

        return {
            "total_articles": len(all_articles),
            "saved_count": saved_count,
        }

    return await run_in_threadpool(_collect_news)


@router.get("/list")
async def list_info(
    source_type: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(50),
):
    """収集済み情報を一覧取得"""
    def _list_info():
        repo = InfoCollectorRepository()
        info_list = repo.search_info(source_type=source_type, query=query, limit=limit)

        return {
            "total_count": len(info_list),
            "items": [
                {
                    "id": info.id,
                    "source_type": info.source_type,
                    "title": info.title,
                    "url": info.url,
                    "snippet": info.snippet,
                    "published_at": info.published_at.isoformat()
                    if info.published_at
                    else None,
                    "fetched_at": info.fetched_at.isoformat(),
                    "source_name": info.source_name,
                }
                for info in info_list
            ],
        }

    return await run_in_threadpool(_list_info)


@router.post("/summary")
async def generate_summary(request: SummaryRequest):
    """収集した情報を要約"""
    def _generate_summary():
        summarizer = InfoSummarizer()

        if request.query:
            result = summarizer.summarize_by_query(
                query=request.query, limit=request.limit, use_llm=request.use_llm
            )
        else:
            result = summarizer.summarize_recent(
                source_type=request.source_type,
                limit=request.limit,
                use_llm=request.use_llm,
            )

        return result

    return await run_in_threadpool(_generate_summary)


@router.delete("/cleanup")
async def cleanup_old_info(days: int = Query(30)):
    """古い情報を削除"""
    def _cleanup():
        repo = InfoCollectorRepository()
        deleted_count = repo.delete_old_info(days=days)
        return {"deleted_count": deleted_count, "retention_days": days}

    return await run_in_threadpool(_cleanup)


def register_info_routes(app):
    """情報収集ルートを登録"""
    app.include_router(router)
