"""
BASH承認システム（Phase 2）のテスト

このモジュールは以下のテストを含む:
- CommandValidator承認コールバック機能のテスト
- BashApprovalQueue管理機能のテスト
- 承認API（/api/bash/pending, /api/bash/approve）のテスト
- AISecretary承認フローのテスト
"""

import threading
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.bash_executor.validator import CommandValidator
from src.bash_executor.exceptions import CommandNotAllowedError
from src.server.approval_queue import BashApprovalQueue


class TestCommandValidatorApproval:
    """CommandValidatorの承認コールバック機能テスト"""

    def test_whitelist_command_no_callback_needed(self):
        """ホワイトリスト内のコマンドは承認不要で実行可能"""
        validator = CommandValidator(
            allowed_commands=["ls", "pwd"],
            block_patterns=[],
            approval_callback=None,
        )

        # ホワイトリスト内のコマンドは例外を投げない
        validator.validate("ls -la", reason="list files")

    def test_non_whitelist_command_no_callback_raises_error(self):
        """承認コールバックがない場合、ホワイトリスト外コマンドは拒否される"""
        validator = CommandValidator(
            allowed_commands=["ls"],
            block_patterns=[],
            approval_callback=None,
        )

        with pytest.raises(CommandNotAllowedError, match="許可されていないコマンドです: rm"):
            validator.validate("rm -rf /", reason="dangerous command")

    def test_approval_callback_approves_command(self):
        """承認コールバックがTrueを返すとコマンドが承認される"""
        approval_callback = Mock(return_value=True)
        validator = CommandValidator(
            allowed_commands=["ls"],
            block_patterns=[],
            approval_callback=approval_callback,
        )

        # 承認コールバックがTrueを返すので例外を投げない
        validator.validate("npm install", reason="install dependencies")

        # コールバックが呼ばれたことを確認
        approval_callback.assert_called_once_with("npm install", "install dependencies")

    def test_approval_callback_rejects_command(self):
        """承認コールバックがFalseを返すとコマンドが拒否される"""
        approval_callback = Mock(return_value=False)
        validator = CommandValidator(
            allowed_commands=["ls"],
            block_patterns=[],
            approval_callback=approval_callback,
        )

        with pytest.raises(CommandNotAllowedError, match="コマンドが拒否されました: npm"):
            validator.validate("npm install", reason="install dependencies")

        approval_callback.assert_called_once()


class TestBashApprovalQueue:
    """BashApprovalQueueのテスト"""

    def test_add_request(self):
        """承認リクエストを追加できる"""
        queue = BashApprovalQueue()
        request_id = queue.add_request("ls -la", "list files")

        assert isinstance(request_id, str)
        assert len(request_id) > 0

        pending = queue.get_pending_requests()
        assert len(pending) == 1
        assert pending[0].command == "ls -la"
        assert pending[0].reason == "list files"

    def test_approve_request(self):
        """承認リクエストを承認できる"""
        queue = BashApprovalQueue()
        request_id = queue.add_request("npm install", "install deps")

        # 別スレッドで承認を実行
        def approve_later():
            time.sleep(0.1)
            queue.approve(request_id)

        thread = threading.Thread(target=approve_later)
        thread.start()

        # 承認待機
        approved = queue.wait_for_approval(request_id, timeout=1.0)
        thread.join()

        assert approved is True

    def test_reject_request(self):
        """承認リクエストを拒否できる"""
        queue = BashApprovalQueue()
        request_id = queue.add_request("rm -rf /", "dangerous")

        # 別スレッドで拒否を実行
        def reject_later():
            time.sleep(0.1)
            queue.reject(request_id)

        thread = threading.Thread(target=reject_later)
        thread.start()

        # 拒否待機
        approved = queue.wait_for_approval(request_id, timeout=1.0)
        thread.join()

        assert approved is False

    def test_timeout_returns_false(self):
        """タイムアウト時はFalseを返す"""
        queue = BashApprovalQueue()
        request_id = queue.add_request("sleep 10", "long command")

        # 誰も承認しないまま短いタイムアウトで待機
        approved = queue.wait_for_approval(request_id, timeout=0.1)

        assert approved is False

    def test_multiple_requests(self):
        """複数のリクエストを管理できる"""
        queue = BashApprovalQueue()
        request_id1 = queue.add_request("ls", "list")
        request_id2 = queue.add_request("pwd", "print working dir")

        pending = queue.get_pending_requests()
        assert len(pending) == 2

        # 1つ承認
        queue.approve(request_id1)
        approved1 = queue.wait_for_approval(request_id1, timeout=0.1)
        assert approved1 is True

        # もう1つは保留中
        pending = queue.get_pending_requests()
        assert len(pending) == 1
        assert pending[0].request_id == request_id2


class TestBashApprovalAPI:
    """承認API（/api/bash/pending, /api/bash/approve）のテスト"""

    @pytest.fixture
    def client(self):
        """TestClientを作成"""
        from fastapi.testclient import TestClient
        from src.server.app import create_app

        app = create_app()
        return TestClient(app)

    def test_get_pending_requests_empty(self, client):
        """承認待ちリクエストがない場合"""
        response = client.get("/api/bash/pending")
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        # 初期状態では空かもしれないが、存在する必要がある
        assert isinstance(data["requests"], list)

    def test_approve_nonexistent_request(self, client):
        """存在しないリクエストIDの承認は404エラー"""
        response = client.post("/api/bash/approve/nonexistent-id?approved=true")
        assert response.status_code == 404

    def test_approve_request_workflow(self, client):
        """承認リクエスト→承認のワークフロー"""
        from src.server.dependencies import get_bash_approval_queue

        queue = get_bash_approval_queue()
        request_id = queue.add_request("echo hello", "test command")

        # 承認待ちリクエストを取得
        response = client.get("/api/bash/pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data["requests"]) >= 1

        # 承認を実行
        response = client.post(f"/api/bash/approve/{request_id}?approved=true")
        assert response.status_code == 200
        result = response.json()
        assert result["approved"] is True
        assert result["message"] == "Command approved"


class TestAISecretaryApprovalIntegration:
    """AISecretaryの承認統合テスト"""

    @pytest.fixture
    def secretary(self):
        """テスト用AISecretaryを作成"""
        from src.ai_secretary.config import Config
        from src.ai_secretary.secretary import AISecretary

        # Mockを使ったConfig作成
        config = Mock(spec=Config)
        config.ollama = Mock()
        config.ollama.host = "http://localhost:11434"
        config.ollama.model = "test-model"
        config.temperature = 0.7
        config.max_tokens = 2000
        config.coeiroink_api_url = "http://localhost:50032"
        config.audio_output_dir = "outputs/audio"
        config.system_prompt = "You are a helpful AI secretary."

        mock_ollama = Mock()
        mock_coeiro = None  # COEIROINKクライアントは無効化
        mock_bash = Mock()

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config,
                ollama_client=mock_ollama,
                coeiroink_client=mock_coeiro,
                audio_player=None,
                bash_executor=mock_bash,
            )

        return secretary

    def test_request_bash_approval_approved(self, secretary):
        """承認リクエストが承認された場合Trueを返す"""
        with patch("src.server.dependencies.get_bash_approval_queue") as mock_get_queue:
            mock_queue = Mock()
            mock_queue.add_request.return_value = "test-request-id"
            mock_queue.wait_for_approval.return_value = True
            mock_get_queue.return_value = mock_queue

            result = secretary._request_bash_approval("npm install", "install deps")

            assert result is True
            mock_queue.add_request.assert_called_once_with("npm install", "install deps")
            mock_queue.wait_for_approval.assert_called_once_with(
                "test-request-id", timeout=300.0
            )

    def test_request_bash_approval_rejected(self, secretary):
        """承認リクエストが拒否された場合Falseを返す"""
        with patch("src.server.dependencies.get_bash_approval_queue") as mock_get_queue:
            mock_queue = Mock()
            mock_queue.add_request.return_value = "test-request-id"
            mock_queue.wait_for_approval.return_value = False
            mock_get_queue.return_value = mock_queue

            result = secretary._request_bash_approval("rm -rf /", "dangerous")

            assert result is False

    def test_request_bash_approval_error_returns_false(self, secretary):
        """承認リクエスト中にエラーが発生した場合Falseを返す"""
        with patch(
            "src.server.dependencies.get_bash_approval_queue",
            side_effect=Exception("Connection error"),
        ):
            result = secretary._request_bash_approval("ls", "list files")
            assert result is False
