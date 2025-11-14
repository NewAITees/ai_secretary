"""Journal機能の統合テスト

P2実装のBASHスクリプトとBashScriptExecutorの統合テスト
"""

import pytest
import json
import os
from pathlib import Path
from src.bash_executor.script_executor import BashScriptExecutor, BashResult


@pytest.fixture
def test_db_path(tmp_path):
    """テスト用の一時DBパス"""
    db_path = tmp_path / "test_ai_secretary.db"
    os.environ["AI_SECRETARY_DB_PATH"] = str(db_path)
    yield db_path
    # クリーンアップ
    if "AI_SECRETARY_DB_PATH" in os.environ:
        del os.environ["AI_SECRETARY_DB_PATH"]


@pytest.fixture
def executor():
    """BashScriptExecutorのインスタンス"""
    return BashScriptExecutor(scripts_dir=Path("scripts"))


def test_init_db(executor, test_db_path):
    """DB初期化スクリプトのテスト"""
    result = executor.execute("journal/init_db.sh", parse_json=False)

    assert result.success
    assert test_db_path.exists()
    assert "Unified database initialized" in result.stdout


def test_log_entry(executor, test_db_path):
    """エントリ記録のテスト"""
    # DB初期化
    executor.execute("journal/init_db.sh", parse_json=False)

    # エントリ記録
    result = executor.execute(
        "journal/log_entry.sh",
        args=[
            "--title",
            "テスト活動",
            "--details",
            "統合テスト実行中",
            "--meta-json",
            '{"duration_minutes": 30}',
        ],
        parse_json=True,
    )

    assert result.success
    assert result.parsed_json is not None
    assert result.parsed_json["title"] == "テスト活動"
    assert result.parsed_json["details"] == "統合テスト実行中"
    assert '"duration_minutes": 30' in result.parsed_json["meta_json"]


def test_get_entries(executor, test_db_path):
    """エントリ取得のテスト"""
    # DB初期化
    executor.execute("journal/init_db.sh", parse_json=False)

    # エントリ記録
    executor.execute(
        "journal/log_entry.sh",
        args=["--title", "テストエントリ1"],
        parse_json=True,
    )
    executor.execute(
        "journal/log_entry.sh",
        args=["--title", "テストエントリ2"],
        parse_json=True,
    )

    # エントリ取得
    result = executor.execute("journal/get_entries.sh", parse_json=True)

    assert result.success
    assert result.parsed_json is not None
    assert len(result.parsed_json) == 2
    # 両方のエントリが含まれていることを確認（順序は問わない）
    titles = [entry["title"] for entry in result.parsed_json]
    assert "テストエントリ1" in titles
    assert "テストエントリ2" in titles


def test_generate_summary(executor, test_db_path):
    """サマリー生成のテスト"""
    # DB初期化
    executor.execute("journal/init_db.sh", parse_json=False)

    # エントリ記録
    executor.execute(
        "journal/log_entry.sh",
        args=[
            "--title",
            "実装作業",
            "--meta-json",
            '{"duration_minutes": 120}',
        ],
        parse_json=True,
    )

    # サマリー生成
    result = executor.execute("journal/generate_summary.sh", parse_json=True)

    assert result.success
    assert result.parsed_json is not None
    assert "activities" in result.parsed_json
    assert "progress" in result.parsed_json
    assert result.parsed_json["progress"]["entry_count"] == 1


def test_script_not_in_whitelist(executor):
    """ホワイトリスト外のスクリプトは実行できないことを確認"""
    with pytest.raises(ValueError, match="Script not allowed"):
        executor.execute("evil_script.sh")


def test_dangerous_args(executor, test_db_path):
    """危険な引数は拒否されることを確認"""
    executor.execute("journal/init_db.sh", parse_json=False)

    with pytest.raises(ValueError, match="dangerous characters"):
        executor.execute(
            "journal/log_entry.sh",
            args=["--title", "test; rm -rf /"],
        )
