"""BashExecutor初期化テスト."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestBashExecutorInitialization:
    """BashExecutor初期化のテスト"""

    @patch("src.bash_executor.create_executor")
    @patch("src.ai_secretary.secretary.OllamaClient")
    def test_bash_executor_auto_initialization(self, mock_ollama, mock_create_executor):
        """bash_executor未指定時に自動初期化されるか"""
        mock_executor = Mock()
        mock_create_executor.return_value = mock_executor

        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="llama3.1:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Test"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        secretary = AISecretary(config=config, ollama_client=Mock(), coeiroink_client=None)

        mock_create_executor.assert_called_once()
        assert secretary.bash_executor is not None

    @patch("src.bash_executor.create_executor")
    @patch("src.ai_secretary.secretary.OllamaClient")
    def test_bash_executor_initialization_failure(self, mock_ollama, mock_create_executor):
        """BashExecutor初期化失敗時はNoneになるか"""
        mock_create_executor.side_effect = Exception("Initialization failed")

        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="llama3.1:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Test"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        secretary = AISecretary(config=config, ollama_client=Mock(), coeiroink_client=None)

        assert secretary.bash_executor is None
