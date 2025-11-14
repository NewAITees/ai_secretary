# P3実装計画：チャット履歴管理（Pythonベース）

## 概要
AISecretaryの会話履歴をアプリ内で自動保存し、過去セッションの一覧・検索・再開を可能にする。永続化先は既存の統合SQLite (`data/ai_secretary.db`) を使用し、Bash経由の外部スクリプトではなくPythonコードにリポジトリ層を実装して直接制御する。これによりUI/APIの機能拡張が容易になり、チャット機能と履歴管理を一体化できる。

## 目的・成功基準
- 会話開始時にUUIDのセッションIDを生成し、AISecretaryが自動的に履歴を保存/更新する。
- REST API（FastAPI）からセッション一覧・詳細・読み込みを提供する。
- 過去セッションの検索・再開をUI/API経由で行える。
- `tests/test_chat_history.py`と`tests/test_chat_history_integration.py`で主要フローを網羅し、既存テストと合わせてすべて成功する。

## データモデル
シンプルな1テーブル構成で履歴全体をJSON文字列として保持する。

```sql
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    messages_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_chat_session ON chat_history(session_id);
CREATE INDEX idx_chat_updated ON chat_history(updated_at DESC);
```

- `session_id`: UUID v4。AISecretary生成。
- `title`: 最初のユーザーメッセージから抽出（先頭30文字程度）。
- `messages_json`: 以下形式のリストをそのままJSON化して保存。
  ```json
  [
    {"role": "user", "content": "こんにちは"},
    {"role": "assistant", "content": "こんにちは！"}
  ]
  ```
- `created_at`/`updated_at`: ISO文字列。更新時は`updated_at`のみ再設定。

## ディレクトリ/ファイル構成
```
src/chat_history/
  __init__.py
  models.py          # ChatSession dataclass + JSONユーティリティ
  repository.py      # ChatHistoryRepository (CRUD)

src/ai_secretary/secretary.py  # 履歴保存/読み込みを統合
src/server/app.py              # REST APIにチャット履歴エンドポイントを追加

scripts/                  # 既存Bash資産は温存するが、P3ではPython実装を採用

tests/
  test_chat_history.py              # リポジトリ単体テスト
  test_chat_history_integration.py  # AISecretary統合テスト
```

## 実装詳細
### 1. モデル層 (`src/chat_history/models.py`)
- `ChatSession` dataclass
  - fields: `id`, `session_id`, `title`, `messages_json`, `created_at`, `updated_at`。
  - `messages`プロパティで`messages_json`をPythonリストへ変換。
  - `from_messages(session_id, title, messages)`のような補助関数を用意するとテストで便利。

### 2. リポジトリ層 (`src/chat_history/repository.py`)
共通SQLiteパス（`data/ai_secretary.db`）を使う。`ChatHistoryRepository`で次の操作を実装する。
- `create_session(session_id, title, messages)`
  - `messages`は`List[Dict[str, Any]]`を想定。
  - 新規セッション作成。既存セッションがあれば`sqlite3.IntegrityError`を捕捉し例外化。
- `update_session(session_id, messages)`
  - `messages_json`を更新し`updated_at`を`datetime.utcnow()`で上書き。
- `save_or_update(session_id, title, messages)`
  - `create_session`/`update_session`を内部で使い分け。
- `get_session(session_id)`
  - `ChatSession`を返す。存在しない場合`None`。
- `list_sessions(limit)`
  - `updated_at`降順で最大`limit`件。
- `search_sessions(query)`
  - `title LIKE ?`と`messages_json LIKE ?`で簡易検索。
- `delete_session(session_id)`
  - 削除し、削除件数を返す。

### 3. AISecretary統合 (`src/ai_secretary/secretary.py`)
- `ChatHistoryRepository`を初期化し、`self.session_id`を`uuid.uuid4()`で生成。
- `self.session_title`を保持し、最初のユーザーメッセージからタイトル生成 `_generate_title()`。
- `chat()`内で会話履歴 (`self.history`) を更新後、`_save_chat_history()`を呼び出してDBへ反映。
- `load_session(session_id)`メソッドを新設し、過去セッションを読み込んで`self.history`に復元し、以降の会話は同じ`session_id`で保存されるようにする。
- 将来のBash連携を妨げないよう、`BashScriptExecutor`の利用箇所には影響を与えない。

### 4. REST API拡張 (`src/server/app.py`)
FastAPIに以下のエンドポイントを追加。いずれも`ChatHistoryRepository`を都度生成。
- `GET /api/chat/sessions?limit=20`
  - `list_sessions`結果を整形して返す。
- `GET /api/chat/sessions/{session_id}`
  - `get_session`。存在しない場合は404。
- `POST /api/chat/load` (body: `{ "session_id": "..." }`)
  - `get_secretary()`でAISecretaryインスタンスを取得し`load_session()`を呼ぶ。
  - 成功時 `{"status": "loaded", "session_id": ...}`。失敗時404。

### 5. テスト (`tests/`)
- `test_chat_history.py`
  - tmpディレクトリにSQLiteを作成し、Repositoryメソッドを網羅。
  - 作成→取得→更新→検索→削除の順でアサート。
- `test_chat_history_integration.py`
  - `AISecretary`を使い、`chat()`呼び出しで履歴が保存されること、`load_session()`で再開できることを確認。
  - DBはpytest fixtureで一時ファイルを張り替える。

## 手順/タイムライン（目安）
1. **データモデル & DDL適用** (0.5h)
   - マイグレーションスクリプトは不要。`ChatHistoryRepository`初期化時に`CREATE TABLE IF NOT EXISTS`を実行。
2. **リポジトリ実装** (1.5h)
3. **AISecretary更新** (1.5h)
4. **API拡張** (1h)
5. **テスト作成** (2h)
6. **動作確認** (0.5h)

## リスク/留意事項
- `messages_json`のサイズが大きい場合の性能: SQLite TEXT上限(約2GB)内であれば許容。必要に応じてセッションを分割。
- タイトル生成ロジックのサニタイズ: 先頭30文字を切り出し、改行や制御文字を除去する。
- 同期制御: `AISecretary`は単一インスタンス想定。将来マルチセッション化する場合はロックが必要。
- Bash資産との整合: 今回はPython処理で完結するが、将来Bash経由で履歴を閲覧するニーズがあれば追加検討。

## 成功後の拡張案
- FTS5による全文検索ビューを後続フェーズで追加。
- UIから履歴カードを表示するフロントエンドコンポーネントを実装。
- メタ情報（モデル名や推論時間など）を`messages_json`とは別に保存できるよう`meta_json`列を追加。
