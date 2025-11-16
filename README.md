# AI Secretary

Ollamaを活用したローカルAI秘書システム

## 概要

AI Secretaryは、Ollamaを活用してローカル環境で動作するAI秘書システムです。
プライバシーを保護しながら、AIとの対話を通じて様々な業務を支援します。

## アーキテクチャ原則

### 1. 外部システムアクセス
- すべての外部システム連携は **BASHコマンド経由** で実行
- `src/bash_executor/` がホワイトリスト検証・引数サニタイズ・監査ログを担当
- 認証情報は環境変数/設定ファイルで管理（コマンドライン引数での受け渡しを避ける）

### 2. 非同期処理の方針
- **Web API（FastAPI）では `asyncio` を使用しない** → すべて同期エンドポイント
- スケジューラ・バックグラウンドジョブは別プロセス/スレッドで実行可能（Webリクエストと独立）
- WSL内部の情報取得（ブラウザ履歴等）も別プロセスで実行OK

### 3. プロンプト管理
- System Promptは3ステージに分離して外部ファイル化
  - `config/prompts/system_planner.txt`: 計画ステージ
  - `config/prompts/system_executor.txt`: 実行ステージ
  - `config/prompts/system_reviewer.txt`: レビューステージ

詳細は [`plan/TODO.md`](plan/TODO.md) の「設計方針」セクションを参照。

## 機能

- Ollamaとの対話（JSON形式レスポンスが基本）
- 会話履歴の管理
- 設定可能なロギングシステム
- 環境変数による柔軟な設定管理
- 複数モデルの切り替え対応

## TODOリスト機能

- SQLiteベースのTODOリポジトリ（`data/todo.db`）と `GET/POST/PATCH/DELETE /api/todos` エンドポイントを追加し、タイトル/詳細/期限/状態（pending, in_progress, done）を永続化します。
- フロントエンドのTODOボードからAIと人間が同じリストを閲覧・追加・編集・完了・削除可能です。
- `AISecretary` は応答JSONに含まれる `todoActions`（add/update/complete/delete）を解釈してDBへ反映し、会話時に最新TODOをシステムプロンプトへ組み込みます。

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

3. 設定ファイルの編集（オプション）
```bash
# config/app_config.yaml を編集して設定をカスタマイズ
# デフォルト設定でも動作します
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

## 定期削除・定期取り込み（P4）

データ保持ポリシーを自動適用し、ブラウザ履歴などの定期取り込みを運用するスケジューラ機能を実装しました。

### スケジューラの起動

```bash
# スケジューラを起動
./scripts/cleanup/scheduler.sh start

# スケジューラを停止
./scripts/cleanup/scheduler.sh stop

# スケジューラの状態確認
./scripts/cleanup/scheduler.sh status
```

### ジョブ管理

```bash
# ジョブ一覧表示
./scripts/cleanup/list_jobs.sh

# 手動でジョブを実行（ドライラン）
./scripts/cleanup/run_job.sh cleanup_logs --dry-run

# 手動でジョブを実行（実行）
./scripts/cleanup/run_job.sh cleanup_logs
```

### ジョブ定義ファイル

ジョブ定義は `config/jobs/cleanup_jobs.json` で管理されています。

### 監査ログDB初期化

```bash
./scripts/cleanup/init_cleanup_db.sh
```

詳細は [plan/P4_P8_P9_design.md](plan/P4_P8_P9_design.md) を参照。

## AI秘書の機能アクセス（P8）

LLMが安全にツールを呼び出せる権限付きAPIレイヤーを実装しました。

### Tool Executor API

```bash
# ツール一覧取得
curl http://localhost:8000/api/tools/list

# ツール実行（例: get_todos）
curl -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "get_todos",
    "args": {"status": "all", "limit": 5},
    "role": "assistant"
  }'
```

### 監査ログDB初期化

```bash
./scripts/tools/init_tool_audit_db.sh
```

### テストスクリプト

```bash
# サーバーが起動している状態で実行
./scripts/tools/test_tool_executor.sh
```

### ツール定義とロール

- **assistant**: `search_web`, `get_todos` などユーザー対話ツールのみ実行可能
- **system**: `cleanup_*`, `import_*` など定期ジョブツールのみ実行可能
- **admin**: 全ツール実行可能

ツール定義: `config/tools/*.yaml`
権限マップ: `config/tools/capabilities.json`

詳細は [plan/P4_P8_P9_design.md](plan/P4_P8_P9_design.md) を参照。

## 履歴ベース提案（P9）

ユーザ履歴を横断して有用な提案を生成する機能を実装しました。

### 統合履歴取得

```bash
# 全データソースから履歴取得
./scripts/history/get_recent_history.sh --type all --limit 50 --days 7

# 特定のデータソースのみ取得
./scripts/history/get_recent_history.sh --type todo --limit 10 --days 30
```

### 提案生成

```bash
# LLMによる提案生成（Ollama必須）
./scripts/history/generate_suggestions.sh --limit 10 --days 7

# suggestionsテーブル初期化
./scripts/history/init_suggestions_db.sh
```

### Suggestions API

```bash
# 提案一覧取得
curl http://localhost:8000/api/suggestions?limit=10

# フィードバック記録（👍: 1, 👎: -1）
curl -X POST http://localhost:8000/api/suggestions/1/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedback": 1}'

# 提案を非表示
curl -X POST http://localhost:8000/api/suggestions/1/dismiss
```

### Tool Executor経由での提案生成

```bash
curl -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "generate_suggestions",
    "args": {"limit": 5, "days": 7},
    "role": "assistant"
  }'
```

### テスト

```bash
# サーバーが起動している状態で実行
./scripts/history/test_suggestions.sh
```

詳細は [plan/P4_P8_P9_design.md](plan/P4_P8_P9_design.md) を参照。

## テスト

```bash
uv run pytest tests/ -v
```

主要カバレッジ:
- `tests/test_todo_repository.py`: SQLiteベースのTODOリポジトリCRUDを検証。
- `tests/test_todo_api.py`: `/api/todos` の作成/更新/削除フローをFastAPI TestClientで確認。
- `tests/test_todo_llm_integration.py`: LLM応答の `todoActions` がAI秘書経由で永続化されることを保証。

## ライセンス

TBD

## 貢献

TBD
