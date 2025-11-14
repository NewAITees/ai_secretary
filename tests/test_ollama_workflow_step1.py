"""Step 1: 初期応答生成のテスト."""

import pytest
from unittest.mock import Mock, patch
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestStep1InitialResponse:
    """Step 1: 初期応答生成の独立テスト"""

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

        # BashExecutorの自動初期化を無効化
        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"), patch(
            "src.bash_executor.create_executor", side_effect=Exception("Disabled")
        ):
            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=None,  # Step 1のテストではBASH実行不要
            )
            return secretary

    def test_step1_response_with_bash_actions(self, secretary):
        """Step 1: bashActionsを含む応答が生成されるか"""
        # Step 1のモック応答
        step1_response = {
            "text": "現在のディレクトリを確認します",
            "bashActions": [{"command": "pwd", "reason": "ディレクトリ確認"}],
            "speakerUuid": "test-uuid",
            "styleId": 0,
            "speedScale": 1.0,
            "volumeScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
            "outputSamplingRate": 24000,
            "prosodyDetail": [],
        }

        secretary.ollama_client.chat = Mock(return_value=step1_response)

        # BASH実行をスキップするためbash_executorをNoneに設定
        result = secretary._execute_bash_workflow(
            user_message="現在のディレクトリは？",
            initial_response=step1_response,
            max_retry=0,
            enable_verification=False,
        )

        # bashActionsがない場合はそのまま返される
        assert result == step1_response
        assert "bashActions" in result

    def test_step1_response_without_bash_actions(self, secretary):
        """Step 1: bashActionsがない場合はそのまま返す"""
        step1_response = {
            "text": "こんにちは！",
            "speakerUuid": "test-uuid",
            "styleId": 0,
            "speedScale": 1.0,
            "volumeScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
            "outputSamplingRate": 24000,
            "prosodyDetail": [],
        }

        result = secretary._execute_bash_workflow(
            user_message="こんにちは",
            initial_response=step1_response,
            max_retry=0,
            enable_verification=False,
        )

        assert result == step1_response
        assert "bashActions" not in result

    def test_step1_response_with_multiple_bash_actions(self, secretary):
        """Step 1: 複数のbashActionsを含む応答"""
        step1_response = {
            "text": "ディレクトリとファイルを確認します",
            "bashActions": [
                {"command": "pwd", "reason": "現在のディレクトリ確認"},
                {"command": "ls -la", "reason": "ファイル一覧取得"},
                {"command": "cat README.md", "reason": "READMEの内容確認"},
            ],
            "speakerUuid": "test-uuid",
            "styleId": 0,
            "speedScale": 1.0,
            "volumeScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
            "outputSamplingRate": 24000,
            "prosodyDetail": [],
        }

        # bash_executorがNoneの場合はbashActionsがあってもそのまま返される
        result = secretary._execute_bash_workflow(
            user_message="プロジェクト情報を教えて",
            initial_response=step1_response,
            max_retry=0,
            enable_verification=False,
        )

        # bash_executorがNoneなのでinitial_responseがそのまま返る
        assert result == step1_response
        assert "bashActions" in result
        assert len(result["bashActions"]) == 3
