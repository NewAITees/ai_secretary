"""
P5実装デモ: 日次サマリー生成のデモンストレーション
"""

from src.journal import JournalSummarizer

if __name__ == "__main__":
    print("=" * 60)
    print("P5実装デモ: 日次サマリー生成")
    print("=" * 60)
    print()

    summarizer = JournalSummarizer()

    # 1. 構造化データのみ取得（LLM不使用）
    print("【1. 構造化データのみ取得】")
    result_no_llm = summarizer.generate_daily_summary(use_llm=False)
    print(f"日付: {result_no_llm['date']}")
    print(f"記録数: {result_no_llm['statistics']['entry_count']}")
    print(f"TODO関連更新: {result_no_llm['statistics']['linked_todo_updates']}")
    print()

    # 2. LLMを使用した自然言語サマリー生成
    print("【2. LLMを使用した自然言語サマリー】")
    print("※Ollamaが起動していない場合はフォールバックサマリーが生成されます")
    print()
    result_with_llm = summarizer.generate_daily_summary(use_llm=True)
    print(result_with_llm.get("summary", "サマリー生成失敗"))
    print()

    if "error" in result_with_llm:
        print(f"[警告] {result_with_llm['error']}: {result_with_llm.get('details', '')}")

    print("=" * 60)
    print("デモ完了")
    print("=" * 60)
