"""ProactiveChatSchedulerのテストコード"""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.ai_secretary.prompt_templates import ProactivePromptManager
from src.ai_secretary.scheduler import ProactiveChatScheduler


@pytest.fixture
def mock_secretary():
    """モックAISecretaryを作成"""
    secretary = MagicMock()
    secretary.chat.return_value = {
        "voice_plan": {"text": "テスト応答"},
        "audio_path": "/path/to/audio.wav",
        "played_audio": True,
    }
    return secretary


@pytest.fixture
def mock_prompt_manager():
    """モックProactivePromptManagerを作成"""
    manager = MagicMock(spec=ProactivePromptManager)
    manager.generate_prompt.return_value = "テストプロンプト"
    return manager


def test_scheduler_enable_disable(mock_secretary, mock_prompt_manager):
    """スケジューラーの有効/無効化が正常に動作することを確認"""
    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)

    # 初期状態は無効
    assert not scheduler.is_enabled()

    # 有効化
    scheduler.enable()
    assert scheduler.is_enabled()

    # 無効化
    scheduler.disable()
    assert not scheduler.is_enabled()


def test_scheduler_start_stop(mock_secretary, mock_prompt_manager):
    """スケジューラーの開始/停止が正常に動作することを確認"""
    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)

    # 開始
    scheduler.start()
    status = scheduler.get_status()
    assert status["running"] is True

    # 停止
    scheduler.stop()
    status = scheduler.get_status()
    assert status["running"] is False


def test_get_status(mock_secretary, mock_prompt_manager):
    """ステータス取得が正常に動作することを確認"""
    scheduler = ProactiveChatScheduler(
        mock_secretary, mock_prompt_manager, interval_seconds=60
    )
    scheduler.enable()
    scheduler.start()

    status = scheduler.get_status()

    assert status["enabled"] is True
    assert status["running"] is True
    assert status["interval_seconds"] == 60
    assert status["pending_count"] == 0

    scheduler.stop()


def test_message_queue_operations(mock_secretary, mock_prompt_manager):
    """メッセージキューの操作が正常に動作することを確認"""
    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)
    scheduler.enable()
    scheduler.start()

    # タスク実行をシミュレート
    scheduler._run_task()

    # メッセージがキューに追加されたことを確認
    status = scheduler.get_status()
    assert status["pending_count"] == 1

    # メッセージ取得
    messages = scheduler.get_pending_messages()
    assert len(messages) == 1
    assert messages[0]["text"] == "テスト応答"

    # 取得後、キューはクリアされる
    status = scheduler.get_status()
    assert status["pending_count"] == 0

    scheduler.stop()


def test_set_interval(mock_secretary, mock_prompt_manager):
    """実行間隔の変更が正常に動作することを確認"""
    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)

    # デフォルトは300秒
    status = scheduler.get_status()
    assert status["interval_seconds"] == 300

    # 間隔を変更
    scheduler.set_interval(120)
    status = scheduler.get_status()
    assert status["interval_seconds"] == 120

    # 10秒未満はエラー
    with pytest.raises(ValueError):
        scheduler.set_interval(5)


def test_run_task_only_when_enabled(mock_secretary, mock_prompt_manager):
    """有効時のみタスクが実行されることを確認"""
    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)
    scheduler.start()

    # 無効状態でタスク実行
    scheduler._run_task()
    assert mock_secretary.chat.call_count == 0

    # 有効化してタスク実行
    scheduler.enable()
    scheduler._run_task()
    assert mock_secretary.chat.call_count == 1

    scheduler.stop()


def test_error_handling_in_task(mock_secretary, mock_prompt_manager):
    """タスク実行中のエラーハンドリングを確認"""
    # chatメソッドがエラーを発生させる
    mock_secretary.chat.side_effect = Exception("テストエラー")

    scheduler = ProactiveChatScheduler(mock_secretary, mock_prompt_manager)
    scheduler.enable()
    scheduler.start()

    # エラーが発生してもプログラムはクラッシュせず、エラーメッセージがキューに追加される
    scheduler._run_task()

    messages = scheduler.get_pending_messages()
    assert len(messages) == 1
    assert messages[0]["error"] is True
    assert "失敗しました" in messages[0]["text"]

    scheduler.stop()


def test_max_queue_size(mock_secretary, mock_prompt_manager):
    """キューの最大サイズ制限が機能することを確認"""
    scheduler = ProactiveChatScheduler(
        mock_secretary, mock_prompt_manager, max_queue_size=3
    )
    scheduler.enable()
    scheduler.start()

    # 5回タスクを実行
    for _ in range(5):
        scheduler._run_task()

    # キューサイズは最大3
    status = scheduler.get_status()
    assert status["pending_count"] == 3

    scheduler.stop()
