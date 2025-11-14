"""
JournalSummarizer: LLMベースの日次サマリー生成器

設計方針:
- BASHスクリプト経由でSQLiteから構造化データを取得
- OllamaClientを使用して自然言語サマリーを生成
- TODO進捗との横断結合データを活用

関連:
- scripts/journal/generate_summary.sh: 構造化データ取得
- src/ai_secretary/ollama_client.py: LLM推論
- src/bash_executor/script_executor.py: BASH実行基盤
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from src.bash_executor import BashScriptExecutor
from src.ai_secretary.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class JournalSummarizer:
    """LLMベースの日次サマリー生成器"""

    def __init__(
        self,
        bash_executor: Optional[BashScriptExecutor] = None,
        ollama_client: Optional[OllamaClient] = None,
    ):
        """
        初期化

        Args:
            bash_executor: BASHスクリプト実行器（テスト用にDI可能）
            ollama_client: Ollamaクライアント（テスト用にDI可能）
        """
        self.bash_executor = bash_executor or BashScriptExecutor()
        self.ollama_client = ollama_client or OllamaClient()

    def generate_daily_summary(
        self, date: Optional[str] = None, use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        日次サマリー生成

        Args:
            date: 対象日付（YYYY-MM-DD形式、Noneの場合は今日）
            use_llm: LLMを使用して自然言語サマリーを生成するか

        Returns:
            サマリー辞書
            - date: 対象日付
            - raw_data: BASHスクリプトから取得した構造化データ
            - summary: 自然言語サマリー（use_llm=Trueの場合）
            - statistics: 統計情報
        """
        # デフォルトは今日
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Generating summary for {date}")

        # BASH経由で構造化データ取得
        try:
            result = self.bash_executor.execute(
                "journal/generate_summary.sh", args=[date], parse_json=True
            )

            if not result.success:
                logger.error(f"Failed to fetch journal data: {result.stderr}")
                return {
                    "date": date,
                    "error": "データ取得に失敗しました",
                    "details": result.stderr,
                }

            raw_data = result.parsed_json

            # データが空の場合
            if not raw_data or raw_data.get("activities") == []:
                return {
                    "date": date,
                    "summary": f"{date}の記録はありません",
                    "raw_data": raw_data,
                    "statistics": {"entry_count": 0, "linked_todo_updates": 0},
                }

        except Exception as e:
            logger.error(f"Error fetching journal data: {e}")
            return {
                "date": date,
                "error": "データ取得エラー",
                "details": str(e),
            }

        # LLMを使用しない場合は構造化データのみ返す
        if not use_llm:
            return {
                "date": date,
                "raw_data": raw_data,
                "statistics": raw_data.get("progress", {}),
            }

        # LLMで自然言語サマリー生成
        try:
            summary_text = self._generate_llm_summary(raw_data)
            return {
                "date": date,
                "summary": summary_text,
                "raw_data": raw_data,
                "statistics": raw_data.get("progress", {}),
            }
        except Exception as e:
            logger.error(f"Error generating LLM summary: {e}")
            # LLM失敗時はフォールバック（簡易サマリー）
            return {
                "date": date,
                "summary": self._generate_fallback_summary(raw_data),
                "raw_data": raw_data,
                "statistics": raw_data.get("progress", {}),
                "error": f"LLM生成失敗: {str(e)}",
            }

    def _generate_llm_summary(self, raw_data: Dict[str, Any]) -> str:
        """
        LLMで自然言語サマリー生成

        Args:
            raw_data: generate_summary.shから取得した構造化データ

        Returns:
            自然言語サマリー文字列
        """
        # プロンプト構築
        system_prompt = """あなたは日次活動サマリーを生成するアシスタントです。
与えられたJSON形式の活動記録から、簡潔で読みやすい日本語のサマリーを生成してください。

以下の要素を含めてください：
1. 活動の総数と概要
2. 主な活動内容（時系列順）
3. TODO進捗状況（リンクされている場合）
4. 所要時間などのメタ情報（記録されている場合）

出力形式は以下のJSON形式で返してください：
{
    "summary": "自然言語サマリー（日本語）",
    "highlights": ["ハイライト1", "ハイライト2", ...],
    "suggestions": "次のアクションへの提案（任意）"
}
"""

        user_prompt = f"""以下の日次活動データからサマリーを生成してください。

日付: {raw_data['date']}

活動記録:
{json.dumps(raw_data['activities'], ensure_ascii=False, indent=2)}

統計:
{json.dumps(raw_data['progress'], ensure_ascii=False, indent=2)}

TODO進捗:
{json.dumps(raw_data['todo_summary'], ensure_ascii=False, indent=2)}
"""

        # LLM呼び出し
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.ollama_client.chat(messages, return_json=True)

        # レスポンスからサマリー取得
        if isinstance(response, dict):
            summary = response.get("summary", "")
            highlights = response.get("highlights", [])
            suggestions = response.get("suggestions", "")

            # フォーマット整形
            output = summary
            if highlights:
                output += "\n\n【ハイライト】\n"
                for highlight in highlights:
                    output += f"- {highlight}\n"
            if suggestions:
                output += f"\n【次のアクション】\n{suggestions}"

            return output
        else:
            # 予期しないレスポンス形式
            logger.warning(f"Unexpected LLM response format: {type(response)}")
            return str(response)

    def _generate_fallback_summary(self, raw_data: Dict[str, Any]) -> str:
        """
        LLM失敗時のフォールバックサマリー（テンプレートベース）

        Args:
            raw_data: 構造化データ

        Returns:
            簡易サマリー文字列
        """
        date = raw_data["date"]
        activities = raw_data.get("activities", [])
        progress = raw_data.get("progress", {})

        entry_count = progress.get("entry_count", 0)
        todo_updates = progress.get("linked_todo_updates", 0)

        summary = f"【{date}の活動サマリー】\n\n"
        summary += f"記録された活動: {entry_count}件\n"
        summary += f"TODO関連更新: {todo_updates}件\n\n"

        if activities:
            summary += "【活動一覧】\n"
            for activity in activities:
                occurred_at = activity.get("occurred_at", "")
                title = activity.get("title", "")
                details = activity.get("details", "")

                # 時刻のフォーマット（ISO8601 → HH:MM）
                try:
                    dt = datetime.fromisoformat(occurred_at)
                    time_str = dt.strftime("%H:%M")
                except Exception:
                    time_str = occurred_at

                summary += f"- [{time_str}] {title}"
                if details:
                    summary += f": {details}"

                # メタ情報
                meta = activity.get("meta_json", "{}")
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}

                if meta.get("duration_minutes"):
                    summary += f" ({meta['duration_minutes']}分)"

                # TODOリンク
                linked_todos = activity.get("linked_todos", [])
                if linked_todos:
                    todo_titles = [
                        f"#{t['todo_id']} {t['todo_title']}" for t in linked_todos
                    ]
                    summary += f" [TODO: {', '.join(todo_titles)}]"

                summary += "\n"

        return summary
