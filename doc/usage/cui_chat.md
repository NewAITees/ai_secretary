# CUI版AI秘書 使用ガイド

## 概要

CUI版AI秘書は、ターミナル上で動作するコマンドラインインターフェースです。Webブラウザを使わずに、標準入出力でAI秘書とやり取りできます。

### 主な用途

- **自動テスト**: Claude Codeなどのツールが直接実行・検証可能
- **スクリプト統合**: シェルスクリプトやパイプラインに組み込み可能
- **リモート環境**: SSH経由での利用
- **軽量動作**: ブラウザやフロントエンドなしで動作

## 基本的な使い方

### 最小構成で起動（音声なし）

```bash
uv run python scripts/cui_chat.py --no-audio
```

### 音声ありで起動

```bash
uv run python scripts/cui_chat.py
```

**注意**: 音声ありモードでは、COEIROINKが起動している必要があります。

## コマンドラインオプション

### `--no-audio`

音声合成・再生を無効化します。テストやスクリプト統合に最適です。

```bash
uv run python scripts/cui_chat.py --no-audio
```

### `--model <モデル名>`

使用するOllamaモデルを指定します。

```bash
uv run python scripts/cui_chat.py --model llama3.1:8b --no-audio
```

### `--system-prompt <プロンプト>`

カスタムシステムプロンプトを設定します。

```bash
uv run python scripts/cui_chat.py --system-prompt "あなたは親切なアシスタントです。" --no-audio
```

### `--log-level <レベル>`

ログレベルを指定します（DEBUG, INFO, WARNING, ERROR）。

```bash
uv run python scripts/cui_chat.py --log-level DEBUG --no-audio
```

### `--session-id <セッションID>`

既存のチャットセッションを読み込んで会話を再開します。

```bash
uv run python scripts/cui_chat.py --session-id abc-123-def --no-audio
```

### `--auto-approve-bash`

BASHコマンドを自動承認します（テスト用、注意して使用）。

```bash
uv run python scripts/cui_chat.py --auto-approve-bash --no-audio
```

**⚠️ 警告**: このオプションを使用すると、AIが提案するすべてのBASHコマンドが自動的に実行されます。テスト環境以外では使用しないでください。

## 対話コマンド

### 終了コマンド

- `exit`
- `quit`
- `q`
- `Ctrl+D`

### リセットコマンド

- `reset` - 会話履歴をリセットして新規セッションを開始

## 3段階BASHフロー

CUI版でもWeb版と同じ3段階BASHフロー（計画→実行→検証）が利用できます。

### BASH承認の流れ

AIがBASHコマンドの実行を提案すると、以下のようなプロンプトが表示されます：

```
============================================================
🔧 BASH コマンド実行の承認が必要です
============================================================
理由: 現在の日付を取得
コマンド: date +%Y-%m-%d
============================================================
実行を承認しますか？ (y/n):
```

- `y` または `yes`: コマンドを実行
- `n` または `no`: コマンドをスキップ
- `Ctrl+C` または `Ctrl+D`: 承認を中断してスキップ

### 自動承認モード（テスト用）

`--auto-approve-bash` オプションを使用すると、すべてのBASHコマンドが自動的に承認されます。

```bash
uv run python scripts/cui_chat.py --no-audio --auto-approve-bash
```

**注意**: 本番環境では使用せず、テストやCI/CD環境でのみ使用してください。

## 使用例

### 1. 基本的な会話

```bash
$ uv run python scripts/cui_chat.py --no-audio
============================================================
AI秘書（CUI版）
============================================================
終了するには 'exit', 'quit', または Ctrl+D を入力してください。
会話履歴をリセットするには 'reset' を入力してください。
============================================================

You: こんにちは
AI: こんにちは！お手伝いできることがありましたら、いつでもお知らせくださいね。

You: 今日の天気は？
AI: 申し訳ございませんが、私はローカルで動作しているため外部の天気情報にアクセスできません。

You: exit
AI秘書を終了します。
```

### 2. パイプライン統合

```bash
echo "こんにちは" | uv run python scripts/cui_chat.py --no-audio | grep "AI:"
```

### 3. BASH承認フローの使用例

```bash
$ uv run python scripts/cui_chat.py --no-audio
You: 今日の日付を教えて

============================================================
🔧 BASH コマンド実行の承認が必要です
============================================================
理由: 現在の日付を取得
コマンド: date +%Y-%m-%d
============================================================
実行を承認しますか？ (y/n): y
✓ 承認されました。コマンドを実行します...

AI: 今日の日付は2025-11-17です。

You: exit
```

### 4. スクリプトからの呼び出し（自動承認）

```bash
#!/bin/bash
# AI秘書に自動で質問するスクリプト（BASH自動承認）

questions=(
    "今日の日付は？"
    "現在のディレクトリは？"
)

for q in "${questions[@]}"; do
    echo "質問: $q"
    echo "$q" | timeout 30 uv run python scripts/cui_chat.py --no-audio --auto-approve-bash | grep "AI:"
    echo ""
done
```

## 自動テスト

CUI版の動作確認用自動テストスクリプトが用意されています。

```bash
./scripts/test_cui_chat.sh
```

### テスト内容

1. ヘルプ表示の動作確認
2. 基本的な会話の動作確認
3. 複数回の会話の動作確認
4. リセットコマンドの動作確認

## トラブルシューティング

### Ollamaに接続できない

**症状**:
```
Connection refused to http://localhost:11434
```

**解決策**:
```bash
# Ollamaが起動しているか確認
ollama list

# 起動していない場合は起動
ollama serve
```

### COEIROINKに接続できない（音声ありモード）

**症状**:
```
COEIROINKクライアント初期化失敗
```

**解決策**:
```bash
# 音声なしモードで起動
uv run python scripts/cui_chat.py --no-audio

# または、COEIROINKを起動
# (COEIROINKのインストール・起動方法は別途参照)
```

### 音声デバイスエラー（WSL2環境）

**症状**:
```
ALSA lib confmisc.c:855:(parse_card) cannot find card '0'
```

**解決策**:

これは警告であり、`--no-audio`モードでは無視して問題ありません。音声ありモードで使用する場合は、`doc/WSL2_AUDIO_SETUP.md` を参照してください。

## 技術的詳細

### アーキテクチャ

CUI版は既存の`AISecretary`クラスをそのまま利用しています。

```
[User Input] → [CUI Script] → [AISecretary] → [OllamaClient] → [Ollama]
                                    ↓
                         [COEIROINKClient] (optional)
                                    ↓
                            [AudioPlayer] (optional)
```

### 依存関係

- `src.ai_secretary.secretary.AISecretary` - メインロジック
- `src.ai_secretary.config.Config` - 設定管理
- `src.ai_secretary.logger.setup_logger` - ログ設定

### セッション管理

- 各起動時に新しいセッションIDが自動生成されます
- `--session-id`オプションで既存セッションを読み込み可能
- 会話履歴は自動的に`data/chat_history.db`に保存されます

## 関連ドキュメント

- [アーキテクチャ概要](../design/architecture.md)
- [AI秘書設計](../design/secretary.md)
- [WSL2音声設定](../WSL2_AUDIO_SETUP.md)
