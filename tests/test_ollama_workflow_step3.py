"""Step 3: 検証ロジックのテスト."""

import pytest
from unittest.mock import Mock, patch
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestStep3Verification:
    """Step 3: 検証・整合性チェックの独立テスト"""

    @pytest.fixture
    def secretary(self):
        """モックを使ったAISecretaryインスタンス"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "You are a helpful assistant."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=None,
            )
            return secretary

    def test_step3_prompt_generation(self, secretary):
        """Step 3: 検証プロンプトが正しく生成されるか"""
        bash_results = [
            {
                "command": "pwd",
                "reason": "ディレクトリ確認",
                "result": {"stdout": "/home/test\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
                "error": None,
            }
        ]

        response = {"text": "現在のディレクトリは/home/testです"}

        prompt = secretary._build_step3_prompt(
            user_message="現在のディレクトリは？",
            bash_results=bash_results,
            response=response,
        )

        assert "Step 3" in prompt
        assert "検証" in prompt
        assert "pwd" in prompt
        assert "/home/test" in prompt
        assert "success" in prompt
        assert "reason" in prompt

    def test_step3_verification_success(self, secretary):
        """Step 3: 検証成功のケース"""
        bash_results = [
            {
                "command": "ls",
                "reason": "ファイル一覧",
                "result": {
                    "stdout": "file1.py\nfile2.py\n",
                    "stderr": "",
                    "exit_code": "0",
                    "cwd": "/home/test",
                },
                "error": None,
            }
        ]

        response = {"text": "ファイルはfile1.pyとfile2.pyです"}

        verification_response = {
            "success": True,
            "reason": "BASHコマンドは正常に実行され、回答も実行結果を正しく反映しています",
            "suggestion": "",
        }

        secretary.ollama_client.chat = Mock(return_value=verification_response)

        result = secretary._bash_step3_verify(
            user_message="ファイル一覧を教えて",
            bash_results=bash_results,
            response=response,
        )

        assert result["success"] is True
        assert result["reason"] != ""
        assert result["suggestion"] == ""

    def test_step3_verification_failure(self, secretary):
        """Step 3: 検証失敗のケース"""
        bash_results = [
            {
                "command": "ls",
                "reason": "ファイル一覧",
                "result": {
                    "stdout": "file1.py\nfile2.py\n",
                    "stderr": "",
                    "exit_code": "0",
                    "cwd": "/home/test",
                },
                "error": None,
            }
        ]

        # 実行結果を反映していない不適切な回答
        response = {"text": "ファイルは見つかりませんでした"}

        verification_response = {
            "success": False,
            "reason": "実行結果にfile1.pyとfile2.pyが含まれているのに、回答では見つからなかったと述べている",
            "suggestion": "lsコマンドの出力を正確に反映してください",
        }

        secretary.ollama_client.chat = Mock(return_value=verification_response)

        result = secretary._bash_step3_verify(
            user_message="ファイル一覧を教えて",
            bash_results=bash_results,
            response=response,
        )

        assert result["success"] is False
        assert result["reason"] != ""
        assert result["suggestion"] != ""

    def test_step3_json_schema(self, secretary):
        """Step 3: JSONスキーマが正しいか"""
        schema = secretary._get_step3_json_schema()

        assert "success" in schema
        assert "reason" in schema
        assert "suggestion" in schema
        # Step 3ではCOEIROINKフィールドは不要
        assert "speakerUuid" not in schema
