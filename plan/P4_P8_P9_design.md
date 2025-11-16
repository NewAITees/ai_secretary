# P4 / P8 / P9 統合設計書

## 目次

1. [背景と前提](#背景と前提)
2. [P4: 定期削除と定期取り込みの設計](#p4-定期削除と定期取り込みの設計)
3. [P8: AI秘書の機能アクセス設計](#p8-ai秘書の機能アクセス設計)
4. [P9: 履歴ベース提案の設計](#p9-履歴ベース提案の設計)
5. [P4/P8/P9の相互作用](#p4p8p9の相互作用)
6. [実装マイルストン](#実装マイルストン)

---

## 背景と前提

### 統一アーキテクチャ原則

1. **外部機能はBASHコマンド経由で実行**
   - AI秘書は `src/bash_executor/` を経由してすべての外部ツールを呼び出す
   - `CommandExecutor`: 一般的なBASHコマンド実行（ホワイトリスト検証 + `subprocess.run`）
   - `BashScriptExecutor`: 特定スクリプト実行（ホワイトリスト + 引数サニタイズ + JSON解析）

2. **非同期処理の方針**
   - Web API（FastAPI）では `asyncio` を使用しない（すべて同期エンドポイント）
   - スケジューラ・バックグラウンドジョブは別プロセス/スレッドで実行可能
   - WSL内部の情報取得も別プロセスで実行OK（Web APIをブロックしない）

3. **共通DB**
   - `data/ai_secretary.db`（SQLite）を共通データストアとして使用
   - 既存テーブル: `todo_items`, `journal_entries`, `chat_history`, `browser_history`, `collected_info`, `info_summaries`
   - 新規テーブル: `cleanup_jobs`, `tool_audit`, `suggestions`（重複が少ないため新規作成）

4. **スケジューラの設計**
   - 既存の `lifelog-system/scripts/daemon.sh` を参考に、P4専用の軽量スケジューラを構築
   - cronライクなジョブ定義ファイル（JSON）で管理
   - デーモンとして常駐し、定期ジョブを実行

---

## P4: 定期削除と定期取り込みの設計

### 目的

データ保持ポリシーを自動適用し、ブラウザ履歴などの定期取り込みを安全に運用する。

### 1) ポリシー設計

#### 保持期間（例）

| データ種別 | 保持期間 | アクション |
|-----------|---------|----------|
| `browser_history` | 30日 | `archive_then_delete` |
| `outputs/audio/*` | 7日 | `delete` |
| `logs/*` | 14日 | `archive_then_delete` |
| `collected_info` | 45日 | `archive_then_delete` |
| `temp/*` | 3日 | `delete` |

#### アーカイブ先

- `data/archive/{yyyy-mm-dd}/`
- アーカイブはgzip圧縮（`.tar.gz`）して保存

#### 例外ルール

- `is_protected=1` フラグが立つレコードはスキップ
- DBテーブルには `is_protected BOOLEAN DEFAULT 0` カラムを追加

### 2) 対象データ

#### ファイル

- `logs/*` - ログファイル
- `outputs/audio/*` - 音声ファイル
- `outputs/transcripts/*` - 文字起こしファイル
- `lifelog-system/audio/*` - ライフログ音声（一時）

#### DB

- `collected_info` - 古い収集情報
- `info_summaries` - 古いサマリー
- `browser_history` - 古いブラウザ履歴
- `chat_history` - 古いチャット履歴（保護フラグ付きは除外）
- `journal_entries` - 古いジャーナル（保護フラグ付きは除外）
- `todo_items` - 完了済み古いTODO（保護フラグ付きは除外）

#### ブラウザ生データ

- Brave/ChromeのHistoryファイル（インポート後、3日経過した原本を掃除）
- インポート済み判定: `browser_import_log` テーブルで管理

### 3) ジョブ設計

#### スケジューラ構成

```
scripts/cleanup/
├── scheduler.py          # 軽量スケジューラ（cronライク）
├── scheduler.sh          # デーモン制御スクリプト（start/stop/status）
├── run_job.sh            # ジョブ実行ラッパー
├── list_jobs.sh          # ジョブ一覧表示
├── add_job.sh            # ジョブ登録
├── cleanup_files.sh      # ファイル削除ジョブ
├── cleanup_db.sh         # DB削除ジョブ
└── import_brave_history.sh  # Brave履歴取り込みジョブ

config/jobs/
└── cleanup_jobs.json     # ジョブ定義ファイル
```

#### ジョブ定義ファイル（`config/jobs/cleanup_jobs.json`）

```json
{
  "jobs": [
    {
      "name": "cleanup_logs",
      "command": "scripts/cleanup/cleanup_files.sh",
      "args": ["--glob", "logs/*.log", "--days", "14", "--archive"],
      "schedule": "0 2 * * *",
      "enabled": true,
      "dry_run": false
    },
    {
      "name": "cleanup_audio",
      "command": "scripts/cleanup/cleanup_files.sh",
      "args": ["--glob", "outputs/audio/*.wav", "--days", "7"],
      "schedule": "0 3 * * *",
      "enabled": true,
      "dry_run": false
    },
    {
      "name": "cleanup_collected_info",
      "command": "scripts/cleanup/cleanup_db.sh",
      "args": ["--table", "collected_info", "--date-column", "fetched_at", "--days", "45", "--archive"],
      "schedule": "0 4 * * *",
      "enabled": true,
      "dry_run": false
    },
    {
      "name": "import_brave_history",
      "command": "scripts/browser/import_brave_history.sh",
      "args": ["--limit", "200"],
      "schedule": "0 * * * *",
      "enabled": true,
      "dry_run": false
    },
    {
      "name": "cleanup_browser_raw",
      "command": "scripts/cleanup/cleanup_browser_raw.sh",
      "args": ["--days", "3"],
      "schedule": "0 5 * * *",
      "enabled": true,
      "dry_run": false
    }
  ]
}
```

#### 代表ジョブ

1. **`cleanup_files.sh`** - ファイル削除/アーカイブ
   ```bash
   ./scripts/cleanup/cleanup_files.sh --glob "logs/*.log" --days 14 --archive
   ```

2. **`cleanup_db.sh`** - DB削除/アーカイブ
   ```bash
   ./scripts/cleanup/cleanup_db.sh --table collected_info --date-column fetched_at --days 45 --archive
   ```

3. **`import_brave_history.sh`** - Brave履歴取り込み（1時間ごと、200件制限）
   ```bash
   ./scripts/browser/import_brave_history.sh --limit 200
   ```

4. **`cleanup_browser_raw.sh`** - 取り込み済み原本削除
   ```bash
   ./scripts/cleanup/cleanup_browser_raw.sh --days 3
   ```

### 4) 監査ログ

#### ログファイル

- `logs/scheduler_audit.log` - 全ジョブの開始/終了/対象件数/失敗理由を記録

#### DBテーブル（`cleanup_jobs`）

```sql
CREATE TABLE IF NOT EXISTS cleanup_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    files_processed INTEGER DEFAULT 0,
    files_deleted INTEGER DEFAULT 0,
    files_archived INTEGER DEFAULT 0,
    db_rows_deleted INTEGER DEFAULT 0,
    error_message TEXT,
    dry_run BOOLEAN DEFAULT 0
);

CREATE INDEX idx_cleanup_jobs_job_name ON cleanup_jobs(job_name);
CREATE INDEX idx_cleanup_jobs_started_at ON cleanup_jobs(started_at);
```

### 5) 確認フロー

- デフォルトはドライラン（`--dry-run`）をサポート
- 初回はドライランをスケジュール
- UI/CLIで実行予定と結果を確認可能

### 6) API/コマンド

```bash
# ジョブ実行（手動）
./scripts/cleanup/run_job.sh cleanup_logs [--dry-run]

# ジョブ一覧
./scripts/cleanup/list_jobs.sh

# ジョブ登録（ジョブ定義ファイルを更新）
./scripts/cleanup/add_job.sh --name cleanup_temp --command "scripts/cleanup/cleanup_files.sh" --args "--glob temp/* --days 3" --schedule "0 6 * * *"

# スケジューラ起動
./scripts/cleanup/scheduler.sh start

# スケジューラ停止
./scripts/cleanup/scheduler.sh stop

# スケジューラ状態確認
./scripts/cleanup/scheduler.sh status
```

---

## P8: AI秘書の機能アクセス設計

### 目的

LLMが安全にツールを呼び出せる権限付きAPIレイヤーを提供する。

### 1) コンポーネント

#### Tool Registry（ツール登録簿）

- 許可されたBASHコマンドとメタデータを `config/tools/*.yaml` で管理
- 各ツールの定義:
  - `name`: ツール名
  - `command`: BASHコマンド/スクリプトパス
  - `description`: 説明
  - `args_schema`: 引数スキーマ（type, required, enum, pattern）
  - `output_format`: 出力形式（json, text, csv等）
  - `safety_tags`: セーフティタグ（read_only, data_delete, network, expensive等）
  - `timeout`: タイムアウト（秒）

#### Capability Map（権限マップ）

- ロール/コンテキスト → 利用可能ツールのマッピング（`config/tools/capabilities.json`）
- 例:
  - `role=assistant`: `search_web`, `get_todos`, `log_journal` は可能、`cleanup` は不可
  - `role=system`: 定期ジョブのみ（`cleanup_*`, `import_*`）
  - `role=admin`: すべて可能

#### Tool Executor（ツール実行器）

- `BashScriptExecutor` をラップし、以下を実施:
  - 引数スキーマ検証
  - タイムアウト
  - サニタイズ
  - レートリミット
  - 監査ログ

#### Audit + Rate Limit（監査 + レート制限）

- `data/tool_audit.db`（SQLite）に呼び出し履歴を保存
- ツールごと/セッションごとのクォータを設定

### 2) 呼び出しフロー

```
LLM
  ↓
POST /api/tools/execute (JSON)
  ↓
Capability Map で権限チェック
  ↓
Tool Registry で引数検証
  ↓
Tool Executor で実行（BashScriptExecutor経由）
  ↓
監査ログに記録
  ↓
標準JSON (success/stdout/stderr/metrics) を返却
```

### 3) 設計ポイント

#### 引数スキーマ

- `type`: `string`, `int`, `float`, `boolean`, `array`
- `required`: 必須フィールド
- `enum`: 列挙値
- `pattern`: 正規表現パターン（例: `^[a-zA-Z0-9_]+$`）

#### セーフティタグ

- `read_only`: 読み取り専用（データ変更なし）
- `data_delete`: データ削除（ユーザー承認が必要）
- `network`: ネットワークアクセス（レートリミット対象）
- `expensive`: 高コスト処理（1日N回まで）

#### コマンドラッパー

- 非同期禁止方針に合わせ、すべて同期実行
- 必要ならキューイングで直列化

#### 失敗時の扱い

- **retriable**: 429/timeout等、リトライ可能
- **non-retriable**: 引数エラー、権限エラー等、リトライ不可

### 4) 提供インターフェース例

#### Tool Registry（`config/tools/search_web.yaml`）

```yaml
name: search_web
command: scripts/info_collector/search_web.sh
description: DuckDuckGo検索を実行し、結果を返す
args_schema:
  query:
    type: string
    required: true
    pattern: "^.{1,200}$"
  limit:
    type: int
    required: false
    default: 5
    enum: [5, 10, 20]
output_format: json
safety_tags:
  - network
  - expensive
timeout: 30
rate_limit:
  max_calls_per_hour: 60
  max_calls_per_day: 500
```

#### Capability Map（`config/tools/capabilities.json`）

```json
{
  "roles": {
    "assistant": {
      "allowed_tools": [
        "search_web",
        "get_todos",
        "add_todo",
        "log_journal",
        "get_browser_history",
        "generate_summary"
      ],
      "denied_tools": [
        "cleanup_*",
        "delete_*"
      ]
    },
    "system": {
      "allowed_tools": [
        "cleanup_*",
        "import_*"
      ],
      "denied_tools": []
    },
    "admin": {
      "allowed_tools": ["*"],
      "denied_tools": []
    }
  }
}
```

#### API呼び出し例

**リクエスト:**
```bash
curl -X POST http://localhost:8000/api/tools/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "search_web",
    "args": {"query": "LLM セキュリティ", "limit": 5},
    "session_id": "uuid-1234",
    "role": "assistant"
  }'
```

**レスポンス:**
```json
{
  "ok": true,
  "stdout": "[{\"title\": \"...\", \"url\": \"...\"}]",
  "parsed": [
    {"title": "LLMセキュリティの基礎", "url": "https://example.com/llm-security"}
  ],
  "metrics": {
    "elapsed_ms": 1200,
    "tool": "search_web",
    "timestamp": "2025-11-17T12:00:00Z"
  }
}
```

### 5) 監査ログ（`data/tool_audit.db`）

```sql
CREATE TABLE IF NOT EXISTS tool_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    elapsed_ms INTEGER,
    retriable BOOLEAN DEFAULT 0
);

CREATE INDEX idx_tool_audit_session_id ON tool_audit(session_id);
CREATE INDEX idx_tool_audit_tool_name ON tool_audit(tool_name);
CREATE INDEX idx_tool_audit_started_at ON tool_audit(started_at);
```

---

## P9: 履歴ベース提案の設計

### 目的

ユーザ履歴を横断して有用な提案を生成し、重複やノイズを抑制する。

### 1) データ統合

#### 取得元

- `browser_history`（P6）
- `todo_items`, `journal_entries`（P1/P2）
- `collected_info`, `info_summaries`（P7）
- `chat_history`（P3）

#### BASH取得スクリプト

```bash
# 統合履歴取得
./scripts/history/get_recent_history.sh --type web|todo|journal|info --limit N --days D
```

**出力例（JSON）:**
```json
[
  {
    "source": "browser_history",
    "title": "Next.js Documentation",
    "body": "https://nextjs.org/docs",
    "tags": ["programming", "web"],
    "timestamp": "2025-11-17T10:00:00Z",
    "relevance_score": 0.85
  },
  {
    "source": "todo_items",
    "title": "Next.jsプロジェクト設計",
    "body": "新規プロジェクトの設計書作成",
    "tags": ["programming", "project"],
    "timestamp": "2025-11-15T09:00:00Z",
    "relevance_score": 0.90
  }
]
```

#### 正規化フィールド

- `source`: データソース（`browser_history`, `todo_items`, `journal_entries`, `collected_info`, `chat_history`）
- `title`: タイトル
- `body`: 本文/URL
- `tags`: タグ配列
- `timestamp`: タイムスタンプ
- `relevance_score`: 関連度スコア（0.0-1.0）

### 2) 提案パイプライン

#### フィルタリング

- タグ/期間/既読/除外ドメインをフィルタ
- P4の保持期間を尊重（削除予定データは除外）

#### 集約/要約

- 近接イベントをクラスタリングして要約
- LLM orルールベース（類似度計算）

#### 提案生成

- プロンプトテンプレートを3段階に分離:
  1. **コンテキスト整形** (`config/prompts/suggestion_context.txt`)
  2. **候補生成** (`config/prompts/suggestion_generate.txt`)
  3. **重複チェック** (`config/prompts/suggestion_dedupe.txt`)

#### 重複防止

- `suggestions` テーブルを作成
- `hash(source_ids + content)` でユニーク制約
- 過去提示済みをスキップ

#### 優先度付け

- 締切近いTODOや反復閲覧URLをスコアリング
- ユーザフィードバック（👍/👎）を蓄積し再学習

### 3) 評価フロー

#### オフライン評価

- 過去ログを再生し、提案の精度/冗長性を計測

#### オンライン評価

- 提示ごとに `feedback` を記録し、精度をモニタ

#### API提供

- P8の Tool Executor 経由で `generate_suggestions.sh` を呼び出し
- REST API: `GET /api/suggestions`

### 4) DB設計（`suggestions` テーブル）

```sql
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    source_ids TEXT NOT NULL,  -- JSON array of source record IDs
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT,
    relevance_score REAL,
    presented_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    feedback INTEGER,  -- -1: 👎, 0: 未評価, 1: 👍
    dismissed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_suggestions_hash ON suggestions(hash);
CREATE INDEX idx_suggestions_presented_at ON suggestions(presented_at);
CREATE INDEX idx_suggestions_feedback ON suggestions(feedback);
```

### 5) API例

**リクエスト:**
```bash
curl http://localhost:8000/api/suggestions?limit=5
```

**レスポンス:**
```json
{
  "suggestions": [
    {
      "id": 1,
      "title": "Next.jsプロジェクト関連のドキュメント整理",
      "body": "最近3回訪問したNext.js公式ドキュメントと、未完了のTODO「Next.jsプロジェクト設計」を統合して進めませんか？",
      "tags": ["programming", "web", "project"],
      "relevance_score": 0.92,
      "sources": ["browser_history:123", "todo_items:45"]
    }
  ]
}
```

---

## P4/P8/P9の相互作用

### 統一インターフェース

1. **P4 → P9**: 定期削除ジョブがブラウザ履歴を取り込み、P9の入力データ鮮度を担保
2. **P8 → P4**: Capability Mapで「削除系ツール」を `role=system` 限定に設定し、LLM権限を明確化
3. **P8 → P9**: P9のBASH取得/提案生成スクリプトをP8のRegistryに登録し、監査ログを統一

### 監査ログの統合

- P4スケジューラログ（`logs/scheduler_audit.log`）
- P8ツール監査ログ（`data/tool_audit.db`）
- P9提案生成ログ（`data/tool_audit.db` の一部）

すべて統一フォーマットで記録し、突合可能にする。

### 保持期間の統一

- P4のジョブ定義とP9のフィルタは同一の保持期間設定（`config/retention_policy.json`）を参照

---

## 実装マイルストン

### Phase 1: P4最小実装（1週間）

- [x] ジョブ定義ファイル作成（`config/jobs/cleanup_jobs.json`）
- [x] `cleanup_files.sh` 実装（ファイル削除/アーカイブ）
- [x] `cleanup_db.sh` 実装（DB削除/アーカイブ）
- [x] スケジューラ実装（`scripts/cleanup/scheduler.py`）
- [x] 監査ログ実装（`logs/scheduler_audit.log` + `cleanup_jobs` テーブル）
- [x] ドライラン機能実装
- [x] 補助スクリプト実装（`run_job.sh`, `list_jobs.sh`, `init_cleanup_db.sh`）

### Phase 2: P8最小実装（1週間）

- [x] Tool Registry 実装（`config/tools/*.yaml`）
- [x] Capability Map 実装（`config/tools/capabilities.json`）
- [x] Tool Executor 実装（`src/ai_secretary/tool_executor.py`）
- [x] 監査ログ実装（`data/tool_audit.db`）
- [x] `search_web` と `cleanup_logs` を登録
- [x] `/api/tools/execute` エンドポイント実装
- [x] テストスクリプト作成（`scripts/tools/test_tool_executor.sh`）

### Phase 3: P9最小実装（1週間）

- [ ] 共通取得スクリプト実装（`scripts/history/get_recent_history.sh`）
- [ ] 簡易提案テンプレート実装（`config/prompts/suggestion_*.txt`）
- [ ] 重複防止ハッシュ実装（`suggestions` テーブル）
- [ ] P8経由で呼び出し（`generate_suggestions.sh` をRegistry登録）
- [ ] `/api/suggestions` エンドポイント実装

### Phase 4: 拡張（2週間）

- [ ] レートリミット実装
- [ ] ユーザ確認フロー実装（UI/CLI）
- [ ] フィードバック学習実装
- [ ] UI/API整備（フロントエンド統合）
- [ ] 統合テスト・E2Eテスト

---

## 関連ドキュメント

- [CLAUDE.md](../CLAUDE.md) - プロジェクト全体の開発ガイド
- [plan/TODO.md](TODO.md) - タスク管理と設計方針
- [doc/design/bash_executor.md](../doc/design/bash_executor.md) - bash_executor設計書
- [README.md](../README.md) - アーキテクチャ原則

---

## 変更履歴

- 2025-11-17: 初版作成（P4/P8/P9統合設計）
- 2025-11-17: Phase 1（P4最小実装）完了
  - `cleanup_files.sh`, `cleanup_db.sh` 実装
  - `scheduler.py`, `scheduler.sh` 実装
  - 監査ログDB（`cleanup_jobs`テーブル）作成
  - 補助スクリプト（`run_job.sh`, `list_jobs.sh`, `init_cleanup_db.sh`）実装
  - ドライラン動作確認済み
- 2025-11-17: Phase 2（P8最小実装）完了
  - `src/ai_secretary/tool_executor.py` 実装（ToolRegistry, CapabilityManager, ToolExecutor, ToolAuditLogger, RateLimiter）
  - 監査ログDB（`tool_audit`テーブル）作成
  - `/api/tools/execute`, `/api/tools/list` エンドポイント実装
  - `config/tools/*.yaml` ツール定義（search_web, get_todos, cleanup_logs）
  - `config/tools/capabilities.json` 権限マップ
  - テストスクリプト（`scripts/tools/test_tool_executor.sh`）作成
