"""ConfigLoaderのテスト"""

import pytest
from pathlib import Path
from src.bash_executor.config_loader import ConfigLoader


@pytest.fixture
def config_loader() -> ConfigLoader:
    """テスト用のConfigLoader"""
    return ConfigLoader("config/bash_executor/config.yaml")


def test_load_config(config_loader: ConfigLoader) -> None:
    """設定ファイルの読み込み"""
    assert config_loader.config is not None
    assert isinstance(config_loader.config, dict)


def test_get_root_dir(config_loader: ConfigLoader) -> None:
    """ルートディレクトリの取得"""
    root_dir = config_loader.get("executor.root_dir")
    assert root_dir is not None
    assert isinstance(root_dir, str)


def test_get_shell(config_loader: ConfigLoader) -> None:
    """シェルの取得"""
    shell = config_loader.get("executor.shell")
    assert shell == "/bin/bash"


def test_get_timeout(config_loader: ConfigLoader) -> None:
    """タイムアウトの取得"""
    timeout = config_loader.get("executor.timeout")
    assert timeout == 30


def test_get_with_default(config_loader: ConfigLoader) -> None:
    """デフォルト値の取得"""
    value = config_loader.get("nonexistent.key", "default_value")
    assert value == "default_value"


def test_get_block_patterns(config_loader: ConfigLoader) -> None:
    """ブロックパターンの取得"""
    patterns = config_loader.get("security.block_patterns")
    assert isinstance(patterns, list)
    assert "`" in patterns
    assert "$(" in patterns


def test_load_whitelist(config_loader: ConfigLoader) -> None:
    """ホワイトリストの読み込み"""
    whitelist = config_loader.load_whitelist()
    assert isinstance(whitelist, list)
    assert len(whitelist) > 0
    assert "ls" in whitelist
    assert "cd" in whitelist
    assert "echo" in whitelist


def test_whitelist_no_comments(config_loader: ConfigLoader) -> None:
    """ホワイトリストにコメントが含まれないことを確認"""
    whitelist = config_loader.load_whitelist()
    for command in whitelist:
        assert not command.startswith("#")


def test_whitelist_no_empty_lines(config_loader: ConfigLoader) -> None:
    """ホワイトリストに空行が含まれないことを確認"""
    whitelist = config_loader.load_whitelist()
    for command in whitelist:
        assert command.strip() != ""


def test_nonexistent_config_file() -> None:
    """存在しない設定ファイル"""
    with pytest.raises(FileNotFoundError):
        ConfigLoader("nonexistent_config.yaml")


def test_get_nested_value(config_loader: ConfigLoader) -> None:
    """ネストされた設定値の取得"""
    enable_whitelist = config_loader.get("security.enable_whitelist")
    assert enable_whitelist is True
