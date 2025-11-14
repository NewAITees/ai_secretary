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
- [ ] **P3** - #7 チャット履歴保存（`src/ai_secretary/secretary.py`はメモリ保持のみで拡張余地大）
- [ ] **P4** - #8 定期削除処理（jobスケジューラ追加とポリシー定義で完結）
- [ ] **P5** - #6 日次サマリー生成（lifelog-systemの`cli_viewer`が参考になる）
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

### [#7 / P3] チャット履歴を保存する

**タスクリスト:**
- [ ] 会話ログ保存ポリシーの定義
- [ ] データスキーマ設計（会話ID、ユーザー操作、AIアクション、メタデータ）
- [ ] SQLiteテーブル作成
- [ ] Repository層実装
- [ ] `AISecretary`への永続化機能追加（`self.conversation_history`の保存）
- [ ] REST APIエンドポイント実装（履歴取得・検索）
- [ ] BASH経由での履歴操作コマンド作成（保存・検索）
- [ ] 暗号化機能の検討・実装（必要に応じて）
- [ ] フロントエンドUI実装（履歴閲覧）
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由で履歴保存・検索を実行する（例: `./scripts/save_chat.sh` または `./scripts/search_chat.sh "キーワード"`）。

**調査メモ:**
`src/ai_secretary/secretary.py`では`self.conversation_history`がメモリ保持のまま消える。DB/ファイル永続化の追加が未着手。

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

### [#6 / P5] 一日のサマリーを生成する機能を作る

**タスクリスト:**
- [ ] サマリー生成対象データの選定（日次ログ、TODO、チャット履歴等）
- [ ] データ集約パイプライン設計
- [ ] LLMを使った自然言語サマリー生成ロジック実装
- [ ] KPI算出機能実装
- [ ] BASHスクリプト作成（`./scripts/generate_daily_summary.sh --date 2025-11-11`）
- [ ] サマリー保存先の決定・実装
- [ ] 配信チャネル実装（UI/メール/チャット）
- [ ] テストコード作成

**外部システムアクセス方針:**
AI秘書はBASHコマンド経由でサマリー生成を実行する。出力は標準出力またはファイルで受け取る。

**調査メモ:**
`lifelog-system/src/cli_viewer.py`には`show_daily_summary`がありSQLビューも揃っているため、結果をAI秘書が取得するAPI化が容易。

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
