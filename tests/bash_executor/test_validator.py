"""CommandValidatorのテスト"""

import pytest
from src.bash_executor.validator import CommandValidator
from src.bash_executor.exceptions import CommandNotAllowedError, BlockedPatternError


@pytest.fixture
def validator() -> CommandValidator:
    """テスト用のバリデーター"""
    return CommandValidator(
        allowed_commands=["ls", "cd", "echo", "pwd", "cat", "grep"],
        block_patterns=["`", "$("],
    )


def test_valid_command(validator: CommandValidator) -> None:
    """正常なコマンドの検証"""
    validator.validate("ls -la")
    validator.validate("echo 'hello world'")
    validator.validate("cd /tmp && pwd")


def test_blocked_pattern_backtick(validator: CommandValidator) -> None:
    """ブロックされたパターン: バッククォート"""
    with pytest.raises(BlockedPatternError):
        validator.validate("echo `whoami`")


def test_blocked_pattern_dollar(validator: CommandValidator) -> None:
    """ブロックされたパターン: $()"""
    with pytest.raises(BlockedPatternError):
        validator.validate("echo $(ls)")


def test_command_not_allowed(validator: CommandValidator) -> None:
    """許可されていないコマンド"""
    with pytest.raises(CommandNotAllowedError):
        validator.validate("sudo rm -rf /")


def test_command_not_allowed_wget(validator: CommandValidator) -> None:
    """許可されていないコマンド: wget"""
    with pytest.raises(CommandNotAllowedError):
        validator.validate("wget http://example.com")


def test_empty_command(validator: CommandValidator) -> None:
    """空のコマンド"""
    with pytest.raises(ValueError):
        validator.validate("")


def test_whitespace_only_command(validator: CommandValidator) -> None:
    """空白のみのコマンド"""
    with pytest.raises(ValueError):
        validator.validate("   ")


def test_pipe_command(validator: CommandValidator) -> None:
    """パイプを含むコマンド"""
    validator.validate("ls -la | grep test")


def test_multiple_commands_with_semicolon(validator: CommandValidator) -> None:
    """セミコロンで区切られた複数コマンド"""
    validator.validate("cd /tmp; pwd; ls")


def test_command_with_and_operator(validator: CommandValidator) -> None:
    """&&演算子を含むコマンド"""
    validator.validate("echo 'test' && cat /etc/hostname")
