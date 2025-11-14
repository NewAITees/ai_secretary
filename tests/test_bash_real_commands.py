"""BASH実行機能の実用的テスト

このテストでは以下を検証します：
- 一般的なコマンド（ls, pwd, cat, echo等）の実行
- プロジェクト固有機能の実行（TODO管理、音声合成など）
- エラーハンドリング・セキュリティテスト
- 実際のファイルシステムとの統合
"""

import os
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.bash_executor import create_executor


class TestGeneralCommands:
    """一般的なコマンドの実行テスト"""

    @pytest.fixture
    def executor(self, tmp_path):
        """一時ディレクトリを使ったCommandExecutor"""
        return create_executor(root_dir=str(tmp_path))

    def test_pwd_command(self, executor):
        """pwdコマンドの実行"""
        result = executor.execute("pwd")

        assert result["exit_code"] == "0"
        assert executor.root_dir in result["stdout"]
        assert result["stderr"] == ""

    def test_echo_command(self, executor):
        """echoコマンドの実行"""
        result = executor.execute("echo 'Hello World'")

        assert result["exit_code"] == "0"
        assert "Hello World" in result["stdout"]

    def test_ls_command(self, executor, tmp_path):
        """lsコマンドの実行"""
        # テストファイルを作成
        (tmp_path / "test1.txt").write_text("content1")
        (tmp_path / "test2.py").write_text("print('hello')")

        result = executor.execute("ls")

        assert result["exit_code"] == "0"
        assert "test1.txt" in result["stdout"]
        assert "test2.py" in result["stdout"]

    def test_ls_with_options(self, executor, tmp_path):
        """lsコマンドにオプションを付けて実行"""
        (tmp_path / "file.txt").write_text("test")

        result = executor.execute("ls -la")

        assert result["exit_code"] == "0"
        assert "file.txt" in result["stdout"]
        # -laオプションで詳細表示されるはず
        assert "rw-" in result["stdout"] or "total" in result["stdout"]

    def test_cat_command(self, executor, tmp_path):
        """catコマンドでファイル内容を読み込み"""
        test_file = tmp_path / "test.txt"
        content = "This is a test file.\nLine 2\nLine 3"
        test_file.write_text(content)

        result = executor.execute(f"cat {test_file.name}")

        assert result["exit_code"] == "0"
        assert content in result["stdout"]

    def test_mkdir_command(self, executor, tmp_path):
        """mkdirコマンドでディレクトリ作成"""
        result = executor.execute("mkdir test_directory")

        assert result["exit_code"] == "0"
        assert (tmp_path / "test_directory").exists()
        assert (tmp_path / "test_directory").is_dir()

    def test_multiple_commands_with_semicolon(self, executor, tmp_path):
        """セミコロンで複数コマンドを実行"""
        result = executor.execute("mkdir subdir ; cd subdir ; pwd")

        assert result["exit_code"] == "0"
        assert "subdir" in result["stdout"]

    def test_command_with_pipe(self, executor, tmp_path):
        """パイプを使ったコマンド"""
        (tmp_path / "test1.txt").write_text("hello")
        (tmp_path / "test2.py").write_text("world")

        # ls | grep でフィルタリング
        result = executor.execute("ls | grep .txt")

        assert result["exit_code"] == "0"
        assert "test1.txt" in result["stdout"]
        assert "test2.py" not in result["stdout"]


class TestProjectSpecificCommands:
    """プロジェクト固有のコマンド実行テスト"""

    @pytest.fixture
    def executor(self):
        """プロジェクトルートを使ったCommandExecutor"""
        project_root = Path(__file__).parent.parent
        return create_executor(root_dir=str(project_root))

    def test_uv_version(self, executor):
        """uvコマンドでバージョン確認"""
        result = executor.execute("uv --version")

        assert result["exit_code"] == "0"
        assert "uv" in result["stdout"].lower()

    def test_git_status(self, executor):
        """gitコマンドでステータス確認"""
        result = executor.execute("git status")

        # gitリポジトリでない場合はスキップ
        if result["exit_code"] != "0":
            pytest.skip("Not a git repository")

        assert "branch" in result["stdout"].lower() or "ブランチ" in result["stdout"]

    def test_git_log(self, executor):
        """gitコマンドでログ確認"""
        result = executor.execute("git log --oneline -5")

        if result["exit_code"] != "0":
            pytest.skip("Not a git repository")

        assert len(result["stdout"]) > 0

    def test_python_version(self, executor):
        """Pythonバージョン確認"""
        # uv経由でPythonバージョンを確認
        result = executor.execute("python --version 2>&1 || uv run python --version")

        # どちらかが成功すればOK
        assert "Python" in result["stdout"] or result["exit_code"] == "0"

    def test_tree_command_if_available(self, executor):
        """treeコマンドが利用可能な場合のテスト"""
        result = executor.execute("tree -L 1")

        # treeがインストールされていない場合はスキップ
        if "command not found" in result["stderr"] or result["exit_code"] != "0":
            pytest.skip("tree command not available")

        assert len(result["stdout"]) > 0

    def test_find_python_files(self, executor):
        """findコマンドでPythonファイルを検索"""
        result = executor.execute("find src -name '*.py' -type f | head -5")

        if result["exit_code"] == "0" and len(result["stdout"]) > 0:
            assert ".py" in result["stdout"]
            assert "src" in result["stdout"]

    def test_grep_in_source_files(self, executor):
        """grepコマンドでソースコード検索"""
        # AISecretaryクラスを検索
        result = executor.execute("grep -r 'class AISecretary' src/ | head -3")

        if result["exit_code"] == "0":
            assert "AISecretary" in result["stdout"]

    def test_wc_count_lines(self, executor):
        """wcコマンドで行数カウント"""
        result = executor.execute("find src -name '*.py' | wc -l")

        if result["exit_code"] == "0":
            # 数字が含まれているはず
            assert any(char.isdigit() for char in result["stdout"])


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    @pytest.fixture
    def executor(self, tmp_path):
        """テスト用のCommandExecutor"""
        return create_executor(root_dir=str(tmp_path))

    def test_command_not_found(self, executor):
        """存在しないコマンドの実行"""
        with pytest.raises(Exception) as exc_info:
            executor.execute("nonexistent_command_12345")

        assert "not found" in str(exc_info.value).lower() or "whitelist" in str(
            exc_info.value
        ).lower()

    def test_file_not_found(self, executor):
        """存在しないファイルの読み込み"""
        result = executor.execute("cat nonexistent_file.txt")

        # catは失敗するがExecutorはresultを返す
        assert result["exit_code"] != "0"
        assert "No such file" in result["stderr"] or len(result["stderr"]) > 0

    def test_permission_denied(self, executor, tmp_path):
        """権限エラーのハンドリング"""
        # 読み取り不可のファイルを作成（Linuxのみ）
        test_file = tmp_path / "no_permission.txt"
        test_file.write_text("secret")

        try:
            test_file.chmod(0o000)
            result = executor.execute(f"cat {test_file.name}")

            # 権限エラーが発生するはず
            assert result["exit_code"] != "0"
            assert "Permission denied" in result["stderr"] or len(result["stderr"]) > 0

        finally:
            # クリーンアップのため権限を戻す
            test_file.chmod(0o644)

    def test_timeout_handling(self, executor):
        """タイムアウトのハンドリング"""
        # 長時間実行されるコマンド（30秒以上でタイムアウト）
        with pytest.raises(Exception) as exc_info:
            executor.execute("sleep 60")

        assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

    def test_syntax_error_in_command(self, executor):
        """構文エラーのあるコマンド"""
        result = executor.execute("ls ||| grep")

        # bashが構文エラーを返すはず
        assert result["exit_code"] != "0"
        assert len(result["stderr"]) > 0


class TestSecurityRestrictions:
    """セキュリティ制限のテスト"""

    @pytest.fixture
    def executor(self, tmp_path):
        """セキュリティ設定を持つCommandExecutor"""
        return create_executor(root_dir=str(tmp_path))

    def test_dangerous_rm_command_blocked(self, executor):
        """危険なrmコマンドがブロックされるか"""
        with pytest.raises(Exception) as exc_info:
            executor.execute("rm -rf /")

        assert "not allowed" in str(exc_info.value).lower() or "blocked" in str(
            exc_info.value
        ).lower()

    def test_chmod_777_blocked(self, executor):
        """危険なchmodコマンドがブロックされるか"""
        with pytest.raises(Exception) as exc_info:
            executor.execute("chmod 777 .")

        # chmodは許可されていない、または危険な使い方がブロックされる
        assert "not allowed" in str(exc_info.value).lower() or "blocked" in str(
            exc_info.value
        ).lower()

    def test_directory_traversal_blocked(self, executor):
        """ディレクトリトラバーサルがブロックされるか"""
        # ルートディレクトリ外へのアクセス
        with pytest.raises(Exception) as exc_info:
            executor.execute("cd ../../../../etc && cat passwd")

        assert "not allowed" in str(exc_info.value).lower() or "blocked" in str(
            exc_info.value
        ).lower()

    def test_curl_to_external_url_allowed(self, executor):
        """外部URLへのcurlは許可されるか（ホワイトリストに依存）"""
        # curlがホワイトリストにある場合のみ実行
        try:
            result = executor.execute("curl --version")
            if result["exit_code"] == "0":
                # curlが利用可能
                result = executor.execute("curl -I https://httpbin.org/status/200")
                # 実行できるか、またはタイムアウト
                assert result["exit_code"] == "0" or "timeout" in result["stderr"].lower()
        except Exception as e:
            # curlがホワイトリストにない場合
            assert "not allowed" in str(e).lower()


class TestComplexScenarios:
    """複雑なシナリオのテスト"""

    @pytest.fixture
    def executor(self):
        """プロジェクトルートを使ったCommandExecutor"""
        project_root = Path(__file__).parent.parent
        return create_executor(root_dir=str(project_root))

    def test_check_python_dependencies(self, executor):
        """Pythonプロジェクトの依存関係確認"""
        # pyproject.tomlの存在確認
        result = executor.execute("ls pyproject.toml")

        if result["exit_code"] == "0":
            # pyproject.tomlの内容を確認
            result = executor.execute("cat pyproject.toml | head -20")
            assert "dependencies" in result["stdout"] or "name" in result["stdout"]

    def test_count_test_files(self, executor):
        """テストファイルの数をカウント"""
        result = executor.execute("find tests -name 'test_*.py' | wc -l")

        if result["exit_code"] == "0":
            # 数字が返ってくるはず
            count = int(result["stdout"].strip())
            assert count >= 1  # 少なくとも1つのテストファイルが存在

    def test_check_git_branch(self, executor):
        """現在のGitブランチ確認"""
        result = executor.execute("git branch --show-current")

        if result["exit_code"] == "0":
            # ブランチ名が返ってくるはず
            assert len(result["stdout"].strip()) > 0

    def test_list_python_files_in_src(self, executor):
        """srcディレクトリ内のPythonファイル一覧"""
        result = executor.execute("find src -name '*.py' -type f | sort | head -10")

        if result["exit_code"] == "0":
            lines = result["stdout"].strip().split("\n")
            assert len(lines) > 0
            for line in lines:
                if line:  # 空行でない場合
                    assert line.endswith(".py")

    def test_search_for_imports(self, executor):
        """importステートメントを検索"""
        result = executor.execute("grep -r '^import ' src/ | head -5")

        if result["exit_code"] == "0":
            assert "import" in result["stdout"]

    def test_check_config_files(self, executor):
        """設定ファイルの存在確認"""
        result = executor.execute("ls config/*.yaml config/*.txt 2>&1")

        # 設定ファイルが存在するはず
        if result["exit_code"] == "0":
            assert "yaml" in result["stdout"] or "txt" in result["stdout"]


class TestBashIntegrationWithAISecretary:
    """AISecretaryとBASH実行の統合テスト"""

    @pytest.fixture
    def secretary_with_real_bash(self, tmp_path):
        """実際のBashExecutorを持つAISecretary"""
        from src.ai_secretary.secretary import AISecretary
        from src.bash_executor import create_executor

        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "You are a helpful assistant."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        # 実際のBashExecutorを作成
        real_bash_executor = create_executor(root_dir=str(tmp_path))

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=real_bash_executor,
            )
            return secretary

    def test_execute_real_pwd_command(self, secretary_with_real_bash, tmp_path):
        """実際のpwdコマンドを実行"""
        actions = [{"command": "pwd", "reason": "ディレクトリ確認"}]

        results = secretary_with_real_bash._process_bash_actions(actions)

        assert len(results) == 1
        assert results[0]["error"] is None
        assert results[0]["result"]["exit_code"] == "0"
        assert str(tmp_path) in results[0]["result"]["stdout"]

    def test_execute_real_ls_command(self, secretary_with_real_bash, tmp_path):
        """実際のlsコマンドを実行"""
        # テストファイルを作成
        (tmp_path / "test1.txt").write_text("content1")
        (tmp_path / "test2.py").write_text("content2")

        actions = [{"command": "ls", "reason": "ファイル一覧"}]

        results = secretary_with_real_bash._process_bash_actions(actions)

        assert len(results) == 1
        assert results[0]["error"] is None
        assert results[0]["result"]["exit_code"] == "0"
        assert "test1.txt" in results[0]["result"]["stdout"]
        assert "test2.py" in results[0]["result"]["stdout"]

    def test_execute_real_cat_command(self, secretary_with_real_bash, tmp_path):
        """実際のcatコマンドを実行"""
        test_file = tmp_path / "test.txt"
        test_content = "This is test content."
        test_file.write_text(test_content)

        actions = [{"command": "cat test.txt", "reason": "ファイル読み込み"}]

        results = secretary_with_real_bash._process_bash_actions(actions)

        assert len(results) == 1
        assert results[0]["error"] is None
        assert results[0]["result"]["exit_code"] == "0"
        assert test_content in results[0]["result"]["stdout"]
