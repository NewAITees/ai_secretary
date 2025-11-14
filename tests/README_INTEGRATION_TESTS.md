# 実環境統合テスト

このディレクトリには、実際のOllamaサーバーとBASH実行環境を使った統合テストが含まれています。

## テストファイル一覧

### モックテスト（外部サービス不要）
- `test_ollama_three_step_workflow.py` - Ollama三段階ワークフローのモックテスト（19テスト）
- `test_system_prompt.py` - system_prompt機能のテスト（13テスト）
- `test_bash_real_commands.py` - BASH実行機能のテスト

### 実環境統合テスト（外部サービス必要）
- `test_ollama_integration_real.py` - 実際のOllamaサーバーを使った統合テスト

## 実環境統合テストの実行

### 前提条件

1. **Ollamaサーバーが起動していること**
   ```bash
   # Ollamaサーバーを起動（別ターミナル）
   ollama serve
   ```

2. **必要なモデルがインストールされていること**
   ```bash
   # qwen3:8bモデルをインストール
   ollama pull qwen3:8b

   # （オプション）他のモデルもテストする場合
   ollama pull llama3.1:8b
   ```

3. **モデルの確認**
   ```bash
   ollama list
   ```

### テストの実行方法

#### すべての実環境テストを実行
```bash
uv run pytest tests/test_ollama_integration_real.py -v
```

#### 特定のテストクラスのみ実行
```bash
# 基本的な会話テスト
uv run pytest tests/test_ollama_integration_real.py::TestRealOllamaIntegration -v

# BASH統合テスト
uv run pytest tests/test_ollama_integration_real.py::TestRealBashIntegration -v

# 3段階ワークフローテスト
uv run pytest tests/test_ollama_integration_real.py::TestRealThreeStepWorkflow -v
```

#### 遅いテストをスキップ
```bash
uv run pytest tests/test_ollama_integration_real.py -v -m "not slow"
```

#### ログ出力を表示
```bash
uv run pytest tests/test_ollama_integration_real.py -v -s
```

### テストの種類

#### TestRealOllamaIntegration（基本テスト）
- `test_simple_chat` - シンプルな会話
- `test_json_response_structure` - JSON応答構造の検証
- `test_conversation_history` - 会話履歴の保持
- `test_system_prompt_effect` - system_promptの効果確認
- `test_reset_conversation` - 会話履歴のリセット
- `test_model_switch` - モデルの一時切り替え

#### TestRealBashIntegration（BASH統合テスト）
- `test_bash_pwd_command` - pwdコマンド実行
- `test_bash_ls_command` - lsコマンド実行
- `test_bash_error_handling` - エラーハンドリング

#### TestRealThreeStepWorkflow（3段階ワークフロー）
- `test_full_three_step_workflow` - 完全な3段階フロー（検証あり）
- `test_workflow_with_retry` - 再試行が発生するケース

### トラブルシューティング

#### Ollamaサーバーが起動していない
```
SKIPPED - Ollamaサーバーが利用できません
```
→ `ollama serve` でサーバーを起動してください

#### モデルがインストールされていない
```
SKIPPED - qwen3:8bモデルが見つかりません
```
→ `ollama pull qwen3:8b` でモデルをインストールしてください

#### ALSAエラー（音声関連）
```
ALSA lib confmisc.c:855:(parse_card) cannot find card '0'
```
→ これは警告です。テストは音声を無効化しているため、動作に影響しません

### モックテストのみ実行（外部サービス不要）

外部サービスが利用できない環境では、モックテストのみ実行できます：

```bash
# Ollama三段階ワークフローテスト（19テスト）
uv run pytest tests/test_ollama_three_step_workflow.py -v

# system_promptテスト（13テスト）
uv run pytest tests/test_system_prompt.py -v
```

### 全テスト実行

```bash
# モックテストのみ（外部サービス不要）
uv run pytest tests/test_ollama_three_step_workflow.py tests/test_system_prompt.py -v

# 統合テストも含む（Ollamaサーバー必要）
uv run pytest tests/ -v -m "not slow"
```

## テストマーカー

- `@pytest.mark.integration` - 外部サービスが必要な統合テスト
- `@pytest.mark.slow` - 実行に時間がかかるテスト

## 注意事項

- 実環境テストはLLMの応答を使用するため、実行に時間がかかります（1テスト: 20-30秒）
- LLMの応答は非決定的なので、完全に同じ結果が返るとは限りません
- テストは`temperature=0.3`（低め）で実行し、再現性を高めています
- COEIROINK（音声合成）とAudioPlayer（音声再生）はテストでは無効化されています

## 参考リンク

- [Ollama公式ドキュメント](https://github.com/ollama/ollama)
- [pytest公式ドキュメント](https://docs.pytest.org/)
