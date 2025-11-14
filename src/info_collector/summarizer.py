"""
情報要約機能（Ollama統合）

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
関連モジュール:
- src/info_collector/repository.py - データ永続化
- src/ai_secretary/ollama_client.py - LLM統合
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import CollectedInfo, InfoSummary
from .repository import InfoCollectorRepository
from src.ai_secretary.ollama_client import OllamaClient


class InfoSummarizer:
    """収集した情報をLLMで要約"""

    def __init__(
        self,
        repository: Optional[InfoCollectorRepository] = None,
        ollama_client: Optional[OllamaClient] = None,
    ):
        self.repository = repository or InfoCollectorRepository()
        self.ollama_client = ollama_client or OllamaClient()

    def summarize_recent(
        self,
        source_type: Optional[str] = None,
        limit: int = 20,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        最近収集した情報を要約

        Args:
            source_type: ソースタイプでフィルタ（None=全て）
            limit: 最大取得件数
            use_llm: LLMで要約生成するか

        Returns:
            要約結果（summary, raw_data, statistics）
        """
        # 情報取得
        info_list = self.repository.search_info(
            source_type=source_type, limit=limit
        )

        if not info_list:
            return {
                "summary": "収集された情報がありません。",
                "raw_data": [],
                "statistics": {"total_count": 0},
            }

        # 統計情報
        statistics = {
            "total_count": len(info_list),
            "source_types": self._count_by_source_type(info_list),
        }

        # LLM要約
        if use_llm:
            summary_text = self._generate_llm_summary(info_list, source_type)
        else:
            summary_text = self._generate_fallback_summary(info_list, source_type)

        return {
            "summary": summary_text,
            "raw_data": [self._info_to_dict(info) for info in info_list],
            "statistics": statistics,
        }

    def summarize_by_query(
        self, query: str, limit: int = 10, use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        検索クエリで情報を抽出して要約

        Args:
            query: 検索クエリ
            limit: 最大取得件数
            use_llm: LLMで要約生成するか

        Returns:
            要約結果
        """
        # クエリ検索
        info_list = self.repository.search_info(query=query, limit=limit)

        if not info_list:
            return {
                "query": query,
                "summary": f'「{query}」に関する情報は見つかりませんでした。',
                "raw_data": [],
                "statistics": {"total_count": 0},
            }

        # 統計情報
        statistics = {
            "total_count": len(info_list),
            "source_types": self._count_by_source_type(info_list),
        }

        # LLM要約
        if use_llm:
            summary_text = self._generate_llm_summary(info_list, query=query)
        else:
            summary_text = self._generate_fallback_summary(info_list, query=query)

        return {
            "query": query,
            "summary": summary_text,
            "raw_data": [self._info_to_dict(info) for info in info_list],
            "statistics": statistics,
        }

    def _generate_llm_summary(
        self, info_list: List[CollectedInfo], source_type: Optional[str] = None, query: Optional[str] = None
    ) -> str:
        """LLMで要約を生成"""
        # プロンプト構築
        prompt = self._build_summary_prompt(info_list, source_type, query)

        try:
            # Ollama呼び出し
            response = self.ollama_client.generate(
                prompt=prompt,
                system="あなたは情報要約の専門家です。与えられた複数の情報を簡潔にまとめてください。",
            )
            return response.strip()
        except Exception as e:
            print(f"LLM要約エラー: {e}")
            return self._generate_fallback_summary(info_list, source_type, query)

    def _build_summary_prompt(
        self, info_list: List[CollectedInfo], source_type: Optional[str] = None, query: Optional[str] = None
    ) -> str:
        """要約プロンプトを構築"""
        header = "以下の情報を要約してください:\n\n"

        if query:
            header = f'「{query}」に関する情報を要約してください:\n\n'
        elif source_type:
            type_names = {"search": "検索結果", "rss": "RSSフィード", "news": "ニュース記事"}
            header = f'{type_names.get(source_type, source_type)}を要約してください:\n\n'

        items = []
        for i, info in enumerate(info_list[:10], 1):  # 最大10件
            item = f"{i}. {info.title}\n"
            if info.snippet:
                item += f"   {info.snippet[:150]}...\n"
            item += f"   URL: {info.url}\n"
            items.append(item)

        footer = "\n\n【要約の要件】\n"
        footer += "- 主なトピック・傾向を3-5点で整理\n"
        footer += "- 各トピックについて簡潔に説明\n"
        footer += "- 重要な情報は見出しを付けて強調\n"

        return header + "\n".join(items) + footer

    def _generate_fallback_summary(
        self, info_list: List[CollectedInfo], source_type: Optional[str] = None, query: Optional[str] = None
    ) -> str:
        """フォールバック要約（テンプレートベース）"""
        lines = []

        if query:
            lines.append(f'## 「{query}」に関する情報まとめ\n')
        elif source_type:
            type_names = {"search": "検索結果", "rss": "RSSフィード", "news": "ニュース記事"}
            lines.append(f'## {type_names.get(source_type, source_type)}まとめ\n')
        else:
            lines.append("## 収集情報まとめ\n")

        lines.append(f"**収集件数**: {len(info_list)}件\n")

        # ソース別カウント
        source_counts = self._count_by_source_type(info_list)
        if source_counts:
            lines.append("**内訳**:")
            for stype, count in source_counts.items():
                type_names = {"search": "検索", "rss": "RSS", "news": "ニュース"}
                lines.append(f"- {type_names.get(stype, stype)}: {count}件")
            lines.append("")

        # 最新5件の見出し
        lines.append("**主な情報**:")
        for i, info in enumerate(info_list[:5], 1):
            lines.append(f"{i}. {info.title}")
            lines.append(f"   {info.url}")
        lines.append("")

        return "\n".join(lines)

    def _count_by_source_type(self, info_list: List[CollectedInfo]) -> Dict[str, int]:
        """ソースタイプ別カウント"""
        counts = {}
        for info in info_list:
            counts[info.source_type] = counts.get(info.source_type, 0) + 1
        return counts

    def _info_to_dict(self, info: CollectedInfo) -> Dict[str, Any]:
        """CollectedInfoを辞書に変換"""
        return {
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

    def save_summary(
        self, summary_type: str, title: str, summary_text: str, source_info_ids: List[int], query: Optional[str] = None
    ) -> int:
        """要約をDBに保存"""
        summary = InfoSummary(
            summary_type=summary_type,
            title=title,
            summary_text=summary_text,
            source_info_ids=source_info_ids,
            query=query,
        )
        return self.repository.add_summary(summary)
