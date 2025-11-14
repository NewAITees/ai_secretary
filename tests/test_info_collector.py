"""情報収集機能のテスト"""

import pytest
from datetime import datetime
from src.info_collector import (
    InfoCollectorRepository,
    SearchCollector,
    RSSCollector,
    NewsCollector,
    CollectedInfo,
)
from src.info_collector.summarizer import InfoSummarizer


@pytest.fixture
def temp_db(tmp_path):
    """テスト用の一時DBパス"""
    db_path = str(tmp_path / "test_info.db")
    return db_path


@pytest.fixture
def repository(temp_db):
    """テスト用リポジトリ"""
    return InfoCollectorRepository(db_path=temp_db)


def test_repository_initialization(repository):
    """リポジトリ初期化テスト"""
    assert repository.db_path
    # 空の検索でエラーが出ないこと
    results = repository.search_info()
    assert results == []


def test_add_and_retrieve_info(repository):
    """情報追加・取得テスト"""
    info = CollectedInfo(
        source_type="search",
        title="Test Article",
        url="https://example.com/test",
        snippet="This is a test",
        fetched_at=datetime.now(),
    )

    # 追加
    info_id = repository.add_info(info)
    assert info_id is not None

    # 取得
    retrieved = repository.get_info_by_id(info_id)
    assert retrieved is not None
    assert retrieved.title == "Test Article"
    assert retrieved.url == "https://example.com/test"


def test_duplicate_prevention(repository):
    """重複防止テスト"""
    info1 = CollectedInfo(
        source_type="search",
        title="Duplicate Test",
        url="https://example.com/duplicate",
        fetched_at=datetime.now(),
    )
    info2 = CollectedInfo(
        source_type="search",
        title="Duplicate Test Modified",
        url="https://example.com/duplicate",  # 同じURL
        fetched_at=datetime.now(),
    )

    # 1回目は成功
    id1 = repository.add_info(info1)
    assert id1 is not None

    # 2回目は重複でNone
    id2 = repository.add_info(info2)
    assert id2 is None


def test_search_info_by_source_type(repository):
    """ソースタイプでの検索テスト"""
    # 異なるソースタイプで追加
    search_info = CollectedInfo(
        source_type="search",
        title="Search Result",
        url="https://example.com/search",
        fetched_at=datetime.now(),
    )
    rss_info = CollectedInfo(
        source_type="rss",
        title="RSS Entry",
        url="https://example.com/rss",
        fetched_at=datetime.now(),
    )

    repository.add_info(search_info)
    repository.add_info(rss_info)

    # 検索結果のみ取得
    results = repository.search_info(source_type="search")
    assert len(results) == 1
    assert results[0].source_type == "search"


def test_search_info_by_query(repository):
    """クエリでの検索テスト"""
    info1 = CollectedInfo(
        source_type="search",
        title="Python Tutorial",
        url="https://example.com/python",
        snippet="Learn Python programming",
        fetched_at=datetime.now(),
    )
    info2 = CollectedInfo(
        source_type="search",
        title="JavaScript Guide",
        url="https://example.com/js",
        snippet="Learn JavaScript",
        fetched_at=datetime.now(),
    )

    repository.add_info(info1)
    repository.add_info(info2)

    # "Python"で検索
    results = repository.search_info(query="Python")
    assert len(results) == 1
    assert "Python" in results[0].title


def test_delete_old_info(repository):
    """古い情報削除テスト"""
    from datetime import timedelta

    # 古い情報
    old_info = CollectedInfo(
        source_type="search",
        title="Old Article",
        url="https://example.com/old",
        fetched_at=datetime.now() - timedelta(days=40),
    )
    # 新しい情報
    new_info = CollectedInfo(
        source_type="search",
        title="New Article",
        url="https://example.com/new",
        fetched_at=datetime.now(),
    )

    repository.add_info(old_info)
    repository.add_info(new_info)

    # 30日以前を削除
    deleted = repository.delete_old_info(days=30)
    assert deleted == 1

    # 新しい情報のみ残る
    remaining = repository.search_info()
    assert len(remaining) == 1
    assert remaining[0].title == "New Article"


def test_search_collector():
    """SearchCollectorのテスト（実際の検索は実行しない）"""
    collector = SearchCollector()
    assert collector is not None


def test_rss_collector():
    """RSSCollectorのテスト"""
    collector = RSSCollector()
    assert collector is not None


def test_news_collector():
    """NewsCollectorのテスト"""
    collector = NewsCollector()
    assert collector is not None


def test_summarizer_fallback(repository):
    """Summarizerフォールバック要約テスト"""
    # テストデータ追加
    for i in range(3):
        info = CollectedInfo(
            source_type="search",
            title=f"Article {i+1}",
            url=f"https://example.com/{i+1}",
            snippet=f"This is article {i+1}",
            fetched_at=datetime.now(),
        )
        repository.add_info(info)

    # Summarizer（LLMなし）
    summarizer = InfoSummarizer(repository=repository)
    result = summarizer.summarize_recent(limit=10, use_llm=False)

    assert "summary" in result
    assert "raw_data" in result
    assert "statistics" in result
    assert result["statistics"]["total_count"] == 3
    assert "Article" in result["summary"]
