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
- Node.js 18以上 / npm
- Ollama（インストール済み）
- COEIROINK（ローカルAPI）
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
npm install --prefix frontend
```
   - 追加のPythonライブラリが必要な場合は `uv add <package_name>` を利用してください。

3. 環境変数の設定
```bash
cp .env.example .env
# .envファイルを編集して必要な設定を行う
```

### 開発環境のセットアップ

開発用の依存関係をインストール：
```bash
uv sync --all-extras
npm install --prefix frontend
```

## 使用方法

### Webインターフェース（開発モード）

メタランチャーでバックエンド（uvicorn）とフロントエンド（Vite）を同時に起動できます。

```bash
uv run python scripts/dev_server.py
```

- バックエンド: http://localhost:8000
- フロントエンド: http://localhost:5173

※初回は `npm install --prefix frontend` を実行してください。

### Webインターフェース（本番ビルドの配信）

```bash
npm run build --prefix frontend
uv run python -m uvicorn src.server.app:app --host 0.0.0.0 --port 8000
```

`frontend/dist` の静的ファイルを任意のWebサーバーで配信することも可能です。

### Python API からの利用

従来どおり Python コードから直接 `AISecretary` を扱うこともできます。

```python
from ai_secretary.secretary import AISecretary

secretary = AISecretary()
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
│   └── logger.py          # ロギング設定
├── src/server/            # FastAPIアプリケーション
├── frontend/              # TypeScript/React UI
├── scripts/               # 開発補助スクリプト
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
