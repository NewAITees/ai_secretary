"""Step 2: 実行結果を踏まえた回答生成のテスト."""

import pytest
from unittest.mock import Mock, patch
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestStep2ResponseGeneration:
    """Step 2: BASH実行結果を踏まえた回答生成の独立テスト"""

    @pytest.fixture
    def secretary_with_bash(self):
        """BASHエグゼキュータ付きのAISecretaryインスタンス"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "You are a helpful assistant."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        mock_bash_executor = Mock()
        mock_bash_executor.root_dir = "/home/test"
        mock_bash_executor.validator = Mock()
        mock_bash_executor.validator.allowed_commands = {"ls", "pwd", "cat"}

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=mock_bash_executor,
            )
            return secretary

    def test_step2_prompt_generation(self, secretary_with_bash):
        """Step 2: プロンプトが正しく生成されるか"""
        bash_results = [
            {
                "command": "pwd",
                "reason": "ディレクトリ確認",
                "result": {
                    "stdout": "/home/test\n",
                    "stderr": "",
                    "exit_code": "0",
                    "cwd": "/home/test",
                },
                "error": None,
            }
        ]

        prompt = secretary_with_bash._build_step2_prompt(
            user_message="現在のディレクトリは？", bash_results=bash_results
        )

        assert "Step 2" in prompt
        assert "BASH実行結果" in prompt
        assert "/home/test" in prompt
        assert "pwd" in prompt
        assert "bashActions" in prompt  # bashActionsを含めないよう指示

    def test_step2_response_with_coeiroink_disabled(self, secretary_with_bash):
        """Step 2: COEIROINKが無効な場合のレスポンス"""
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

        # COEIROINKが無効な場合のレスポンス
        step2_response = {"text": "ファイルはfile1.pyとfile2.pyです"}
        secretary_with_bash.ollama_client.chat = Mock(return_value=step2_response)

        result = secretary_with_bash._bash_step2_generate_response(
            user_message="ファイル一覧を教えて", bash_results=bash_results
        )

        assert result == step2_response
        assert "text" in result
        # bashActionsは含まれていないはず
        assert "bashActions" not in result

    def test_step2_handles_bash_error(self, secretary_with_bash):
        """Step 2: BASHエラーを適切に処理するか"""
        bash_results = [
            {
                "command": "cat non_existent.txt",
                "reason": "ファイル読み込み",
                "result": None,
                "error": "FileNotFoundError: No such file or directory",
            }
        ]

        step2_response = {"text": "ファイルが見つかりませんでした"}
        secretary_with_bash.ollama_client.chat = Mock(return_value=step2_response)

        result = secretary_with_bash._bash_step2_generate_response(
            user_message="ファイルの内容を教えて", bash_results=bash_results
        )

        assert result["text"] == "ファイルが見つかりませんでした"

    def test_step2_json_schema_with_coeiroink(self, secretary_with_bash):
        """Step 2: COEIROINKが有効な場合のJSONスキーマ"""
        # COEIROINKクライアントを有効化
        secretary_with_bash.coeiro_client = Mock()

        schema = secretary_with_bash._get_step2_json_schema()

        assert "text" in schema
        assert "speakerUuid" in schema
        assert "styleId" in schema
        assert "speedScale" in schema

    def test_step2_json_schema_without_coeiroink(self, secretary_with_bash):
        """Step 2: COEIROINKが無効な場合のJSONスキーマ"""
        # COEIROINKクライアントを無効化
        secretary_with_bash.coeiro_client = None

        schema = secretary_with_bash._get_step2_json_schema()

        assert "text" in schema
        # COEIROINKフィールドは含まれない
        assert "speakerUuid" not in schema or schema.count("speakerUuid") == 0
