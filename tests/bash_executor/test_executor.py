"""CommandExecutorのテスト"""

import pytest
from pathlib import Path
from src.bash_executor.executor import CommandExecutor
from src.bash_executor.validator import CommandValidator
from src.bash_executor.exceptions import TimeoutError


@pytest.fixture
def executor(tmp_path: Path) -> CommandExecutor:
    """テスト用のExecutor"""
    validator = CommandValidator(
        allowed_commands=["ls", "cd", "echo", "pwd", "sleep", "mkdir", "touch"],
        block_patterns=["`", "$("],
    )

    return CommandExecutor(root_dir=str(tmp_path), validator=validator, timeout=2)


def test_simple_command(executor: CommandExecutor) -> None:
    """シンプルなコマンドの実行"""
    result = executor.execute("echo 'test'")
    assert "test" in result["stdout"]
    assert result["exit_code"] == "0"


def test_pwd_command(executor: CommandExecutor, tmp_path: Path) -> None:
    """pwdコマンドの実行"""
    result = executor.execute("pwd")
    assert str(tmp_path) in result["stdout"]


def test_directory_change(executor: CommandExecutor, tmp_path: Path) -> None:
    """ディレクトリ移動"""
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    result = executor.execute(f"cd subdir && pwd")
    # 注: cdの動作はシェルセッションごとに独立しているため、
    # cwdの追跡が正しく動作することを確認
    assert executor.get_cwd() == str(tmp_path)


def test_get_cwd(executor: CommandExecutor, tmp_path: Path) -> None:
    """現在の作業ディレクトリの取得"""
    cwd = executor.get_cwd()
    assert cwd == str(tmp_path)


def test_command_with_stderr(executor: CommandExecutor) -> None:
    """stderrを含むコマンド"""
    result = executor.execute("ls /nonexistent_directory_12345")
    assert result["stderr"] != ""
    assert result["exit_code"] != "0"


def test_timeout(executor: CommandExecutor) -> None:
    """タイムアウトのテスト"""
    with pytest.raises(TimeoutError):
        executor.execute("sleep 10")


def test_result_structure(executor: CommandExecutor) -> None:
    """結果の構造確認"""
    result = executor.execute("echo 'test'")
    assert "stdout" in result
    assert "stderr" in result
    assert "cwd" in result
    assert "exit_code" in result


def test_create_file(executor: CommandExecutor, tmp_path: Path) -> None:
    """ファイル作成"""
    executor.execute("touch test_file.txt")
    assert (tmp_path / "test_file.txt").exists()


def test_create_directory(executor: CommandExecutor, tmp_path: Path) -> None:
    """ディレクトリ作成"""
    executor.execute("mkdir test_dir")
    assert (tmp_path / "test_dir").exists()
    assert (tmp_path / "test_dir").is_dir()
