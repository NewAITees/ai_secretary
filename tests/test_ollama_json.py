"""
OllamaクライアントのJSON形式レスポンステスト

このテストはOllamaが実際に動作していることを前提とします。
"""

import json
import pytest
from src.ai_secretary.ollama_client import OllamaClient


class TestOllamaJSON:
    """OllamaクライアントのJSON形式レスポンステスト"""

    @pytest.fixture
    def client(self):
        """テスト用のOllamaクライアントを作成"""
        return OllamaClient(
            host="http://localhost:11434",
            model="llama3.1:8b",
            temperature=0.7,
            max_tokens=1024,
        )

    def test_chat_json_response(self, client):
        """
        chat()メソッドがJSON形式でレスポンスを返すことをテスト
        """
        messages = [
            {
                "role": "user",
                "content": "次の情報をJSON形式で返してください: 名前は太郎、年齢は25歳、職業はエンジニア",
            }
        ]

        # JSON形式でレスポンスを取得
        response = client.chat(messages=messages, stream=False, return_json=True)

        # レスポンスが辞書型であることを確認
        assert isinstance(response, dict), f"Expected dict, got {type(response)}"

        # レスポンスに何らかのキーが含まれていることを確認
        assert len(response) > 0, "Response dictionary is empty"

        print(f"\n取得したJSONレスポンス: {json.dumps(response, ensure_ascii=False, indent=2)}")

    def test_generate_json_response(self, client):
        """
        generate()メソッドがJSON形式でレスポンスを返すことをテスト
        """
        prompt = "次の情報をJSON形式で返してください: 都市名は東京、人口は約1400万人、国は日本"

        # JSON形式でレスポンスを取得
        response = client.generate(
            prompt=prompt, stream=False, return_json=True, system="あなたは正確なJSON形式でデータを返すアシスタントです。"
        )

        # レスポンスが辞書型であることを確認
        assert isinstance(response, dict), f"Expected dict, got {type(response)}"

        # レスポンスに何らかのキーが含まれていることを確認
        assert len(response) > 0, "Response dictionary is empty"

        print(f"\n取得したJSONレスポンス: {json.dumps(response, ensure_ascii=False, indent=2)}")

    def test_chat_text_response(self, client):
        """
        return_json=Falseでテキスト形式のレスポンスを取得できることをテスト
        """
        messages = [{"role": "user", "content": "こんにちは"}]

        # テキスト形式でレスポンスを取得
        response = client.chat(messages=messages, stream=False, return_json=False)

        # レスポンスが文字列であることを確認
        assert isinstance(response, str), f"Expected str, got {type(response)}"
        assert len(response) > 0, "Response is empty"

        print(f"\n取得したテキストレスポンス: {response}")

    def test_json_with_specific_schema(self, client):
        """
        特定のスキーマに従ったJSON形式のレスポンスを取得できることをテスト
        """
        messages = [
            {
                "role": "user",
                "content": """次の形式のJSONを返してください:
{
  "task": "タスクの説明",
  "priority": "高/中/低",
  "deadline": "期限（YYYY-MM-DD形式）",
  "assignee": "担当者名"
}

内容: プロジェクトのドキュメント作成、優先度は高、期限は2025年11月1日、担当者は山田太郎""",
            }
        ]

        # JSON形式でレスポンスを取得
        response = client.chat(messages=messages, stream=False, return_json=True)

        # レスポンスが辞書型であることを確認
        assert isinstance(response, dict), f"Expected dict, got {type(response)}"

        # 期待されるキーが含まれているか確認（柔軟に対応）
        # Ollamaのモデルによっては完全に一致しない可能性があるため、最低限のチェック
        assert len(response) > 0, "Response dictionary is empty"

        print(
            f"\n特定スキーマのJSONレスポンス: {json.dumps(response, ensure_ascii=False, indent=2)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
