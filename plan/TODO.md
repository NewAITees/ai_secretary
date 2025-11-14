# TODOリスト（優先順位付き）

## 設計方針：外部システムアクセス

**LLM秘書が外部システムやサービスにアクセスする際の統一要件:**
- すべての外部システム連携は **BASHコマンドを通じて実行** する
- 各機能は単独で実行可能なBASHスクリプトまたはコマンドとして提供する
- AI秘書は `subprocess` 経由でこれらのコマンドを呼び出し、標準出力/標準エラー出力を解析する
- 認証情報やAPIキーは環境変数または設定ファイルで管理し、コマンドライン引数での受け渡しを避ける

この方針により、AI秘書は統一されたインターフェース（BASH実行）で多様なツールを利用できるようになる。

---

## 優先度サマリー（チェックリスト形式）

- [x] **P1** - #2 TODOリスト操作（既存DBとAPIに小規模テーブル追加で着手可能）
- [x] **P2** - #3 「今日やったこと」記録（lifelog-systemのログ設計を流用できる）
- [x] **P3** - #7 チャット履歴保存（Pythonベースの自動保存機能として実装完了）
- [ ] **P4** - #8 定期削除処理（jobスケジューラ追加とポリシー定義で完結）
- [x] **P5** - #6 日次サマリー生成（LLMベースの自然言語サマリー生成機能として実装完了）
- [ ] **P6** - #1 ウェブ履歴のDB格納（lifelog-systemに将来拡張案ありだが未実装）
- [ ] **P7** - #10 ネット検索連携（外部I/Oが必要でサンドボックス配慮が必要）
- [ ] **P8** - #4 AI秘書の機能アクセス設計（権限情報整理とAPI化で規模中）
- [ ] **P9** - #5 履歴を元にした提案（推論ロジックと評価ループ構築が必要）
- [ ] **P10** - #9 能動会話の高度化（対話制御の刷新で最も複雑）

以下、各タスクの詳細と調査メモ。

---

### [#2 / P1] ✅ TODOリストを操作できるようにする（完了）

**タスクリスト:**
- [x] 既存データストア内にTODOエンティティを追加し、作成/更新/削除/完了フローを設計する
- [x] CLIまたはUIから操作できるAPIを公開し、AI秘書からも利用できるインターフェースを整える
- [x] BASH経由でのTODO操作コマンドを実装する（例: `uv run python -m src.todo.cli add "タスク名"`）
- [x] テストコードを作成し動作を検証する

**実装内容 (2025-11-11完了):**
- `src/todo/`以下にSQLiteリポジトリを追加
- `/api/todos` CRUDエンドポイント + フロントUIを実装
- `AISecretary`はTODOコンテキストを会話へ注入し、`todoActions`でAI側から登録/更新/完了が可能
- `tests/test_todo_repository.py`・`tests/test_todo_api.py`・`tests/test_todo_llm_integration.py`でストレージ/REST/LLM連携の動作をカバー

### [#3 / P2] ✅ 「今日やったこと」を記録する（統合スキーマ対応・完了）

**タスクリスト:**
- [x] 統合スキーマ設計（P1と同一SQLiteインスタンス、`todo_items` + `journal_entries`）
- [x] 既存TODOデータのマイグレーション（`scripts/journal/migrate_todos.sh`）
- [x] BASH経由の統合DB初期化スクリプト作成（`scripts/journal/init_db.sh`）
- [x] BASH経由のエントリ記録スクリプト作成（`scripts/journal/log_entry.sh`）
- [x] BASH経由のエントリ取得スクリプト作成（`scripts/journal/get_entries.sh`）
- [x] BASH経由のエントリ検索スクリプト作成（`scripts/journal/search_entries.sh`）
- [x] BASH経由のTODOリンクスクリプト作成（`scripts/journal/link_todo.sh`）
- [x] BASH経由のサマリー生成スクリプト作成（`scripts/journal/generate_summary.sh` - 横断結合対応）
- [x] BashScriptExecutor実装（subprocess安全実行基盤）
- [x] 既存TODO実装の統合スキーマ対応（`src/todo/repository.py`, `src/todo/models.py`）
- [x] テストコード作成（BashExecutor/スクリプト統合）

**実装内容 (2025-11-14完了):**

#### 作成ファイル
- `scripts/journal/init_db.sh` - 統合DB初期化（todo_items + journal_entries + ビュー）
- `scripts/journal/migrate_todos.sh` - 既存TODOデータ移行
- `scripts/journal/log_entry.sh` - エントリ記録（タグ・TODOリンク対応）
- `scripts/journal/get_entries.sh` - エントリ取得（日付指定）
- `scripts/journal/search_entries.sh` - エントリ検索（日付範囲・タグ・TODO）
- `scripts/journal/link_todo.sh` - TODO⇄実績リンク
- `scripts/journal/generate_summary.sh` - 日次サマリー生成（横断結合）
- `src/bash_executor/script_executor.py` - BashScriptExecutor実装
- `tests/test_journal_integration.py` - 統合テスト（全6テスト通過）

#### 更新ファイル
- `src/bash_executor/__init__.py` - BashScriptExecutor/BashResultをエクスポート
- `src/todo/models.py` - TodoStatus拡張（todo/doing/done/archived）、priority/tags_json追加
- `src/todo/repository.py` - 統合スキーマ対応（todo_items使用、data/ai_secretary.db）

#### 統合スキーマ構成
- **統合DB**: `data/ai_secretary.db`
- **TODOテーブル**: `todo_items`（priority, tags_json追加）
- **ジャーナルテーブル**: `journal_entries`（活動記録）
- **タグテーブル**: `journal_tags`, `journal_entry_tags`（多対多）
- **リンクテーブル**: `journal_todo_links`（TODO⇄実績の横断結合）
- **ビュー**: `v_daily_progress`（日次進捗）、`v_todo_latest_journal`（TODO最新実績）

#### 使い方

**1. DB初期化（初回のみ）**
```bash
./scripts/journal/init_db.sh
```

**2. 活動記録**
```bash
# 基本的な記録
./scripts/journal/log_entry.sh --title "Python学習" --details "型ヒントについて学んだ"

# メタデータ付き（所要時間など）
./scripts/journal/log_entry.sh \
  --title "実装作業" \
  --details "P2機能実装完了" \
  --meta-json '{"duration_minutes": 120, "energy_level": 4}'

# タグ付き
./scripts/journal/log_entry.sh \
  --title "コードレビュー" \
  --tags "work,review"

# TODOとリンク
./scripts/journal/log_entry.sh \
  --title "P2実装完了" \
  --todo-ids "1,2,3"
```

**3. 記録の取得**
```bash
# 今日の記録
./scripts/journal/get_entries.sh

# 特定日の記録
./scripts/journal/get_entries.sh 2025-11-14
```

**4. 記録の検索**
```bash
# 日付範囲
./scripts/journal/search_entries.sh --start-date 2025-11-01 --end-date 2025-11-14

# タグ検索
./scripts/journal/search_entries.sh --tag "work"

# TODO関連
./scripts/journal/search_entries.sh --todo-id 1

# タイトル検索
./scripts/journal/search_entries.sh --title-pattern "実装"
```

**5. 日次サマリー**
```bash
# 今日のサマリー
./scripts/journal/generate_summary.sh

# 特定日のサマリー
./scripts/journal/generate_summary.sh 2025-11-14
```

**6. Python経由での使用（AISecretary統合予定）**
```python
from src.bash_executor import BashScriptExecutor

executor = BashScriptExecutor()

# エントリ記録
result = executor.execute(
    "journal/log_entry.sh",
    args=["--title", "会議", "--details", "週次MTG"],
    parse_json=True
)
print(result.parsed_json)

# サマリー取得
result = executor.execute("journal/generate_summary.sh", parse_json=True)
print(result.parsed_json)
```

**セキュリティ対策:**
- ホワイトリスト方式（許可されたスクリプトのみ実行可能）
- 引数サニタイズ（危険な文字列を検出・拒否）
- タイムアウト設定（デフォルト30秒）

**詳細設計:**
`plan/P2_DAILY_LOG_PLAN_v2.md`参照（統合スキーマ版）

**次のステップ（TODO）:**
- [ ] AISecretaryへのjournal機能統合（会話からの記録・検索）
- [ ] 日次ログコンテキストの会話への注入
- [ ] LLM統合テストの作成

### [#7 / P3] ✅ チャット履歴を保存する（Pythonベース・完了）

**タスクリスト:**
- [x] 会話ログ保存ポリシーの定義（セッション単位、JSON形式）
- [x] データスキーマ設計（session_id, title, messages_json, timestamps）
- [x] SQLiteテーブル作成（chat_historyテーブル）
- [x] Repository層実装（ChatHistoryRepository）
- [x] `AISecretary`への永続化機能追加（自動保存・セッション読み込み）
- [ ] REST APIエンドポイント実装（履歴取得・検索）※次フェーズ
- [ ] ~~BASH経由での履歴操作コマンド作成~~（不要：Pythonコードで直接実装）
- [ ] 暗号化機能の検討・実装（必要に応じて）※後回し
- [ ] フロントエンドUI実装（履歴閲覧）※次フェーズ
- [x] テストコード作成（24テスト全て通過）

**実装内容 (2025-11-14完了):**

#### 作成ファイル
- `src/chat_history/__init__.py` - モジュール初期化
- `src/chat_history/models.py` - ChatSessionデータモデル
- `src/chat_history/repository.py` - ChatHistoryRepository（CRUD操作）
- `tests/test_chat_history.py` - リポジトリ単体テスト（14テスト）
- `tests/test_chat_history_integration.py` - AISecretary統合テスト（10テスト）

#### 更新ファイル
- `src/ai_secretary/secretary.py`:
  - ChatHistoryRepository統合
  - `session_id`/`session_title`管理
  - `chat()`メソッドで自動保存
  - `load_session()`メソッドで過去セッション読み込み
  - `reset_conversation()`で新セッション生成

#### スキーマ構成
```sql
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,     -- UUIDv4
    title TEXT NOT NULL,                 -- 最初のメッセージから生成（30文字）
    messages_json TEXT NOT NULL,         -- JSON配列で会話全体を保存
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_chat_session ON chat_history(session_id);
CREATE INDEX idx_chat_updated ON chat_history(updated_at DESC);
```

#### 主要機能
- **自動保存**: `chat()`呼び出しごとに履歴を自動保存
- **セッション管理**: UUID形式のセッションIDで一意に識別
- **タイトル自動生成**: 最初のメッセージから自動生成（最大30文字）
- **会話継続**: `load_session()`で過去の会話を読み込んで継続可能
- **検索機能**: タイトル・メッセージ内容でセッション検索（Repository層）

#### 使い方

**Python API経由（AISecretary）**
```python
from src.ai_secretary import AISecretary

secretary = AISecretary()

# 新規会話（自動保存）
secretary.chat("こんにちは")
session_id = secretary.session_id  # 現在のセッションID

# 会話リセット（新しいセッション）
secretary.reset_conversation()

# 過去のセッション再開
secretary.load_session(session_id)
secretary.chat("続きの質問")  # 会話が継続される
```

**Repository直接操作**
```python
from src.chat_history import ChatHistoryRepository

repo = ChatHistoryRepository()

# セッション一覧取得（新しい順）
sessions = repo.list_sessions(limit=20)

# セッション検索
results = repo.search_sessions("Python")

# セッション取得
session = repo.get_session(session_id)
messages = session.messages  # パース済みメッセージリスト
```

**設計方針の変更:**
当初計画ではBASHスクリプト経由での保存・検索を想定していたが、チャット履歴は会話ごとにリアルタイム保存する必要があるため、**Pythonコードで直接実装**する方針に変更。
- BASH経由での呼び出しは外部ツール向けに不要（内部統合のため）
- AISecretaryクラスに直接統合し、会話フローに組み込む
- REST APIは次フェーズで実装予定

**詳細設計:**
`plan/P3_CHAT_HISTORY_PLAN.md`参照（Pythonベース版）

**次のステップ（TODO）:**
- [ ] REST APIエンドポイント実装（`GET /api/chat/sessions`, `GET /api/chat/sessions/{id}`, `POST /api/chat/load`）
- [ ] フロントエンドUI実装（履歴一覧・検索・再開機能）
- [ ] セッションメタデータ拡張（モデル名、推論時間など）
- [ ] 暗号化機能検討（機密情報を含む会話の保護）

### [#8 / P4] 履歴や音声などのファイルを定期削除する

**タスクリスト:**
- [ ] データ保持期間ポリシーの定義
- [ ] 削除対象ファイルの判定ロジック実装
- [ ] BASH削除スクリプト作成（`./scripts/cleanup_old_files.sh --days 30`）
- [ ] スケジューラー機能実装（cronまたはPythonベース）
- [ ] 削除前アーカイブ機能の検討・実装
- [ ] 監査ログ機能実装
- [ ] ユーザー確認フローの検討
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由で削除スクリプトを実行する。cronジョブとして登録する場合もBASHスクリプトを用いる。

**調査メモ:**
`lifelog-system`にデーモンとスケジューラが既に存在するため、同等のジョブ登録方式を流用できる可能性あり。

---

### [#6 / P5] ✅ 一日のサマリーを生成する機能を作る（完了）

**タスクリスト:**
- [x] サマリー生成対象データの選定（日次ログ、TODO、チャット履歴等）
- [x] データ集約パイプライン設計
- [x] LLMを使った自然言語サマリー生成ロジック実装
- [x] KPI算出機能実装
- [x] BASHスクリプト作成（`./scripts/generate_daily_summary.sh --date 2025-11-11`）※P2で完了
- [x] テストコード作成

**実装内容 (2025-11-14完了):**

#### 作成ファイル
- `src/journal/__init__.py` - journalモジュール初期化
- `src/journal/summarizer.py` - JournalSummarizer（LLMベースのサマリー生成器）
- `tests/test_journal_summarizer.py` - JournalSummarizer単体テスト（7テスト通過）
- `tests/test_ai_secretary_summary.py` - AISecretary統合テスト（4テスト通過）

#### 更新ファイル
- `src/ai_secretary/secretary.py`:
  - `get_daily_summary(date, use_llm)` メソッド追加
  - JournalSummarizerとの統合
  - datetimeインポート追加

#### 主要機能

**1. JournalSummarizer**
- BASH経由でSQLiteから構造化データ取得（`scripts/journal/generate_summary.sh`利用）
- OllamaClientでLLM推論による自然言語サマリー生成
- LLM失敗時のフォールバックサマリー生成（テンプレートベース）
- TODO進捗との横断結合データ活用

**2. 生成されるサマリー内容**
- 活動総数と概要
- 主な活動内容（時系列順）
- TODO進捗状況（リンクされている場合）
- 所要時間などのメタ情報
- ハイライト（LLM生成時）
- 次のアクションへの提案（LLM生成時）

#### 使い方

**AISecretary経由での使用**
```python
from src.ai_secretary.secretary import AISecretary

secretary = AISecretary()

# 今日のサマリー（LLM使用）
summary = secretary.get_daily_summary()
print(summary["summary"])

# 特定日のサマリー（LLM使用）
summary = secretary.get_daily_summary(date="2025-11-14", use_llm=True)

# 構造化データのみ（LLM不使用）
data = secretary.get_daily_summary(use_llm=False)
print(data["raw_data"])
```

**JournalSummarizer直接使用**
```python
from src.journal import JournalSummarizer

summarizer = JournalSummarizer()

# サマリー生成
result = summarizer.generate_daily_summary(date="2025-11-14", use_llm=True)
print(result["summary"])
```

#### サマリーレスポンス形式

```json
{
    "date": "2025-11-14",
    "summary": "【自然言語サマリー】\n本日はPython学習を2時間実施しました...",
    "raw_data": {
        "date": "2025-11-14",
        "activities": [...],
        "progress": {"entry_count": 2, "linked_todo_updates": 1},
        "todo_summary": [...]
    },
    "statistics": {
        "entry_count": 2,
        "linked_todo_updates": 1
    }
}
```

#### 設計上の特徴

1. **P2との統合**
   - P2で実装された`scripts/journal/generate_summary.sh`を再利用
   - 統合DB（`data/ai_secretary.db`）からTODO⇄実績の横断結合データを取得
   - ビュー（`v_daily_progress`, `v_todo_latest_journal`）を活用

2. **LLM連携**
   - OllamaClientでJSON形式の構造化レスポンスを取得
   - プロンプトエンジニアリングで高品質なサマリー生成
   - LLM失敗時のフォールバック機構（テンプレートベース）

3. **テスト戦略**
   - BashExecutor/OllamaClientのモック化
   - エッジケース（空データ、エラー、LLM失敗）のカバー
   - AISecretary統合テストで実運用フローを検証

#### テスト結果
- `tests/test_journal_summarizer.py`: 7テスト全て通過
- `tests/test_ai_secretary_summary.py`: 4テスト全て通過

**次のステップ（今後の拡張）:**
- [ ] REST APIエンドポイント実装（`GET /api/summary/{date}`）
- [ ] フロントエンドUI実装（サマリー表示ダッシュボード）
- [ ] サマリー保存・履歴管理機能
- [ ] 週次/月次サマリー生成機能
- [ ] メール/チャット配信機能

---

### [#1 / P6] ウェブサイトの閲覧履歴をDBに格納する

**タスクリスト:**
- [ ] 収集対象ブラウザの選定（Chrome/Firefox等）
- [ ] ブラウザ履歴取得方法の調査・実装
- [ ] データスキーマ設計（時刻・URL・タイトル・メタ情報）
- [ ] SQLiteテーブル作成
- [ ] Repository層実装
- [ ] BASH取得スクリプト作成（`./scripts/import_browser_history.sh --browser chrome`）
- [ ] 定期取り込みジョブ実装
- [ ] 重複排除ロジック実装
- [ ] REST APIエンドポイント実装（履歴参照）
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由でブラウザ履歴取得を実行する。

**調査メモ:**
`lifelog-system/README.md`の「今後の拡張」にブラウザ履歴統合が記載されているがコードは未実装。新規Collectorが必要。

---

### [#10 / P7] ネット検索で最新情報を取得する

**タスクリスト:**
- [ ] 検索エンジンAPI選定（DuckDuckGo/Google Custom Search等）
- [ ] サンドボックス化された検索コネクタ実装
- [ ] BASH検索スクリプト作成（`./scripts/web_search.sh "検索クエリ"`）
- [ ] 結果要約機能実装（LLM活用）
- [ ] キャッシュ機能実装
- [ ] レート制限機能実装
- [ ] 利用規約順守チェック機構
- [ ] AI秘書からの検索インターフェース追加
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由で検索を実行する。結果はJSON形式で標準出力に返す。

**調査メモ:**
既存コードにHTTP検索コネクタは確認できず、新規で安全な外部アクセスレイヤーを設計する必要がある。

---

### [#4 / P8] AI秘書が各種機能にアクセスする方法を設計する

**タスクリスト:**
- [ ] AIエージェント用APIレイヤー設計
- [ ] 権限管理仕様の策定
- [ ] ツール呼び出しAPIの実装
- [ ] プロンプトエンジニアリング（各機能の利用ケース設計）
- [ ] `subprocess`経由のBASHコマンド実行基盤実装
- [ ] レート制限機能実装
- [ ] 監査ログ機能実装
- [ ] 外部サービス連携の安全装置実装
- [ ] テストコード作成

**外部システムアクセス方針:**
すべての外部機能はBASHコマンド経由で実行可能にする。AI秘書は`subprocess`モジュールでコマンドを呼び出し、結果を解析する統一インターフェースを持つ。

**調査メモ:**
FastAPI層（`src/server/app.py`）はシンプルな`/api/chat`のみ。将来のツール呼び出しAPIを追加する設計作業が必要。

---

### [#5 / P9] AI秘書が履歴を受け取り提案できるようにする

**タスクリスト:**
- [ ] 履歴統合仕様の策定（ウェブ/TODO/日次ログ等）
- [ ] 履歴要約ストリーム設計
- [ ] BASH履歴取得スクリプト作成（`./scripts/get_recent_history.sh --type web --limit 100`）
- [ ] 提案生成アルゴリズム設計
- [ ] LLMプロンプトテンプレート作成
- [ ] 重複提案防止機構実装
- [ ] ユーザーフィードバック学習機能設計・実装
- [ ] 評価フロー構築
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由で履歴取得を実行する。結果はJSON形式で受け取る。

**調査メモ:**
提案ロジックや学習フローは未定義。履歴統合とプロンプトテンプレートの設計が大きな作業となる。

---

### [#9 / P10] 能動的な会話を複雑化し面白くする

**タスクリスト:**
- [ ] 対話状態管理機能の改善
- [ ] 話題転換ロジック実装
- [ ] 多段プランニング機能実装
- [ ] 文脈保持力強化
- [ ] エンタメ要素追加（小ネタ、雑談テンプレート）
- [ ] 素材取得BASHスクリプト作成（天気情報、ニュース等）
- [ ] ユーザー設定UI実装
- [ ] 既存能動会話機能の大幅改修
- [ ] テストコード作成

**外部システムアクセス方針:**
会話の素材取得（天気情報、ニュースなど）はBASHコマンド経由で実行する（例: `./scripts/get_weather.sh`、`./scripts/get_news_headlines.sh`）。

**調査メモ:**
`src/ai_secretary/scheduler.py`と`prompt_templates.py`が既存の能動会話機能。ここを大幅改修する必要があるため最下位優先。
