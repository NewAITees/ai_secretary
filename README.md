# AI Secretary

Ollamaを活用したローカルAI秘書システム

## 概要

AI Secretaryは、Ollamaを活用してローカル環境で動作するAI秘書システムです。
プライバシーを保護しながら、AIとの対話を通じて様々な業務を支援します。

## 機能

- Ollamaとの対話（JSON形式レスポンスが基本）
- 会話履歴の管理
- 設定可能なロギングシステム
- 環境変数による柔軟な設定管理
- 複数モデルの切り替え対応

## セットアップ

### 必要要件

- Python 3.13以上
- Ollama（インストール済み）
- uv（Pythonパッケージマネージャー）

### インストール

1. リポジトリのクローン
```bash
git clone <repository_url>
cd ai_secretary
```

2. uvで依存関係をインストール
```bash
uv sync
```

3. 環境変数の設定
```bash
cp .env.example .env
# .envファイルを編集して必要な設定を行う
```

### 開発環境のセットアップ

開発用の依存関係をインストール：
```bash
uv sync --all-extras
```

## 使用方法

```python
from ai_secretary import AISecretary
from ai_secretary.config import Config
from ai_secretary.logger import setup_logger

# ロガーのセットアップ
setup_logger()

# 秘書システムの起動
secretary = AISecretary()
secretary.start()

# JSON形式で応答を取得
response = secretary.chat("今日のタスクを教えてください", return_json=True)
print(response)
```

## プロジェクト構造

```
ai_secretary/
├── src/ai_secretary/      # メインパッケージ
│   ├── __init__.py        # パッケージ初期化
│   ├── config.py          # 設定管理
│   ├── secretary.py       # メイン秘書クラス
│   ├── ollama_client.py   # Ollama APIクライアント
│   └── logger.py          # ロギング設定
├── tests/                 # テストコード
├── doc/                   # ドキュメント
├── plan/                  # 計画・タスク管理
├── logs/                  # ログファイル（自動生成）
├── pyproject.toml         # プロジェクト設定
└── README.md              # このファイル
```

## テスト

```bash
uv run pytest tests/ -v
```

## ライセンス

TBD

## 貢献

TBD
