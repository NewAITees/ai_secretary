"""
ニュースサイトコレクター

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/models.py - NewsArticle
- src/info_collector/repository.py - データ永続化

NOTE: 現在はBeautifulSoup4による基本的なスクレイピング実装。
      JavaScript必須サイトにはplaywright-mcpを使用する拡張が可能。
"""

from typing import List, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from ..models import NewsArticle
from .base import BaseCollector


class NewsCollector(BaseCollector):
    """ニュースサイトからの情報収集器"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def collect(self, site_url: str, max_articles: int = 10) -> List[NewsArticle]:
        """
        ニュースサイトから記事を取得

        Args:
            site_url: ニュースサイトのURL
            max_articles: 最大取得記事数

        Returns:
            ニュース記事のリスト
        """
        try:
            response = requests.get(
                site_url, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            soup = BeautifulSoup(response.text, "html.parser")
            site_name = self._extract_site_name(site_url, soup)

            articles = self._extract_articles(soup, site_url, site_name)
            return articles[:max_articles]

        except Exception as e:
            print(f"ニュース取得エラー ({site_url}): {e}")
            return []

    def collect_multiple(
        self, site_urls: List[str], max_articles_per_site: int = 10
    ) -> List[NewsArticle]:
        """
        複数のニュースサイトから一括取得

        Args:
            site_urls: ニュースサイトURLのリスト
            max_articles_per_site: サイトあたりの最大取得記事数

        Returns:
            全サイトの記事リスト
        """
        all_articles = []
        for url in site_urls:
            articles = self.collect(url, max_articles=max_articles_per_site)
            all_articles.extend(articles)
        return all_articles

    def _extract_site_name(self, url: str, soup: BeautifulSoup) -> str:
        """サイト名を抽出"""
        # titleタグから取得を試みる
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()

        # ドメイン名を使用
        parsed = urlparse(url)
        return parsed.netloc

    def _extract_articles(
        self, soup: BeautifulSoup, base_url: str, site_name: str
    ) -> List[NewsArticle]:
        """
        HTMLから記事を抽出（汎用的なヒューリスティック）

        NOTE: サイト固有の抽出ロジックは必要に応じて追加可能
        """
        articles = []

        # 汎用的な記事要素を探す
        # <article>, <h2><a>, <h3><a> などの一般的なパターン
        article_elements = soup.find_all("article") or []

        # articleタグがない場合はh2/h3内のリンクを試す
        if not article_elements:
            for tag in ["h2", "h3"]:
                headers = soup.find_all(tag)
                for header in headers:
                    link = header.find("a")
                    if link and link.get("href"):
                        articles.append(
                            self._create_article_from_link(
                                link, base_url, site_name
                            )
                        )

        # articleタグがある場合
        for article in article_elements:
            # タイトルとリンクを探す
            title_elem = article.find(["h1", "h2", "h3", "h4"])
            link_elem = article.find("a")

            if title_elem and link_elem:
                title = title_elem.get_text().strip()
                url = urljoin(base_url, link_elem.get("href"))

                # 抜粋テキストを探す
                snippet = ""
                p_tag = article.find("p")
                if p_tag:
                    snippet = p_tag.get_text().strip()

                # 画像を探す
                img_url = None
                img_tag = article.find("img")
                if img_tag and img_tag.get("src"):
                    img_url = urljoin(base_url, img_tag.get("src"))

                articles.append(
                    NewsArticle(
                        title=title,
                        url=url,
                        snippet=snippet,
                        image_url=img_url,
                        source_name=site_name,
                        fetched_at=datetime.now(),
                    )
                )

        return articles

    def _create_article_from_link(
        self, link_elem, base_url: str, site_name: str
    ) -> NewsArticle:
        """リンク要素から記事オブジェクトを作成"""
        title = link_elem.get_text().strip()
        url = urljoin(base_url, link_elem.get("href"))

        return NewsArticle(
            title=title,
            url=url,
            source_name=site_name,
            fetched_at=datetime.now(),
        )
