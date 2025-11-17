# P10 能動会話高度化 設計

## 目的とスコープ
- ユーザー操作がなくても状況に応じた提案・実行を行う能動会話を「材料収集→計画→実行→フォローアップ」の多段フローに刷新する。ただし毎回すべてを集約せず、時間帯とランダム性で必要素材を間引く。
- 外部連携はすべてBASH経由とし、DBに蓄積された履歴・収集情報を文脈として活用する。
- Web/CUIの両UIからON/OFFや頻度・話題の好みを切り替えられるようにする。
- スコープ外: 音声ストリーミング、リアルタイムWebSocket配信（今回はHTTPポーリングのまま）。

## 要求事項（整理）
- リッチさ: 時事・進捗・TODO・習慣など複数視点を「時刻帯×確率」で組み合わせ、毎回違うコンビネーションにする。
- 多段プランニング: 1ターン内で「プラン生成→必要データ取得（BASH/DBを必要分だけサンプリング）→提案生成」を自律実行。
- 文脈保持: チャット履歴/ジャーナル/ブラウザ履歴/収集情報から確率的に一部を採用し、重い取得を回避。
- 安全性: すべての外部行為はToolExecutor/BashScriptExecutor経由で承認・監査する。
- 多様性/飽き防止: 話題カテゴリをラウンドロビンし、同種の提案ハッシュが近接しないよう制御。
- ユーザー設定: 頻度、話題カテゴリON/OFF、トーン（仕事/雑談）、自動実行許可範囲を設定可能。
- 記録と評価: 実行ログとユーザー評価を保存し、次回以降の話題選択に反映。

## 全体アーキテクチャ
```
ProactiveOrchestrator (新)
  ├─ Trigger Engine          # ルール/時刻/状態で起動可否判定（時間帯ごとの発火確率と抑制）
  ├─ Topic Planner           # 話題カテゴリ決定 + 多段プラン生成（素材は確率的にサブセット選択）
  ├─ Context Aggregator      # BASH/DBで材料収集（選択された素材のみ）
  ├─ Action Executor         # ToolExecutor経由でBASH実行・結果格納
  ├─ Response Composer       # LLMで提案文生成（system_executor/system_reviewer利用）
  └─ Feedback Tracker        # 提案とフィードバックをDB保存

Data/Config
  - data/ai_secretary.db
      proactive_runs        # 実行ログ（topic, plan, executed_commands, summary, feedback_id）
      proactive_feedback    # ユーザー評価（useful/boring/defer等）
      user_preferences      # 能動会話設定（frequency, topics_enabled, tone, auto_exec_policy）
  - config/proactive_topics/*.yaml  # 話題カテゴリ設定（必要素材・優先度・抑制条件）
  - config/prompts/system_*        # 既存3ステージプロンプトを再利用し、P10専用追加差分を持つ
Scripts (BASH材料取得)
  - scripts/history/get_recent_history.sh        # 既存（履歴統合）
  - scripts/info_collector/generate_summary.sh   # 既存（収集情報要約）
  - scripts/journal/generate_summary.sh          # 既存（日次サマリー）
  - scripts/proactive/get_weather.sh             # 新規（天気/気温のJSON取得・ローカル優先）
  - scripts/proactive/get_headlines.sh           # 新規（ニュース見出し上位N件をJSONで返す）
  - scripts/proactive/get_agenda.sh              # 新規（当日TODO/ジャーナル予定を整形）
  - scripts/proactive/get_fun_snippets.sh        # 新規（雑談ネタ/小ネタをローテーション）
```

## コンポーネント詳細

### 1) Trigger Engine
- 入力: 現在時刻、ユーザープレファレンス、エラーバックオフ状態、前回実行のtopic。
- 判定例:
  - 時刻帯ルール: 朝/昼/夕で発火確率と上限回数を設定（user_preferences.frequency_profile）。
  - 抑制ルール: 直近30分に手動チャットが連続している場合スキップ、連続NG回数で指数バックオフ。
  - 重複防止: 同topicをN回連続しない、同一suggestion_hashは24h抑制。

### 2) Topic Planner
- 話題カテゴリ（例）: `progress_check`, `short_break`, `news_digest`, `weather`, `todo_followup`, `entertainment`.
- 各カテゴリは `config/proactive_topics/*.yaml` で「候補素材（bashコマンド名・DBビュー）」「生成すべきアウトプット型」「抑制条件」を宣言。
- Plannerはカテゴリ選択後、LLM（system_planner）で「取るべきアクション列」を計画し、素材はtime-of-dayと確率でサブセット選択（例: 朝はnews40%/weather80%/agenda90%、夜はnews20%/fun60%）。

### 3) Context Aggregator
- 計画で指定された素材のうち抽選で選ばれたものだけを取得し、正規化JSONでLLMに渡す。
- 取得手段:
  - BASH: `get_recent_history.sh`, `generate_summary.sh`, `get_weather.sh`, `get_headlines.sh`, `get_agenda.sh`, `get_fun_snippets.sh`（必要分のみ）。
  - DB直読: 軽量ビュー（例: 未完TODO件数、最新ジャーナル3件、最近のsuggestionsフィードバック）。
- 失敗時: エラーをplan上にマークし、代替（雑談）にフォールバック。

### 4) Action Executor
- Plannerが出した「実行コマンド」をToolExecutorに渡し、BashScriptExecutor経由で実行。
- コマンドは `config/tools/*.yaml` に登録（`proactive_get_weather`, `proactive_get_headlines` など）。引数スキーマと許可ロールを明示。
- 実行結果は `proactive_runs.executed_commands` にJSONで保存（command, args, stdout, stderr, exit_code, started_at, finished_at）。

### 5) Response Composer
- system_executor + system_reviewerプロンプトにP10差分を追記し、材料JSONとplanトレースを入力。
- 出力フォーマット:
  - `main_text`: ユーザーに返す本文（50–120字程度、トーンはuser_preferences.toneに従う）
  - `next_actions`: 提案アクション配列（type: `ask`, `do`, `open_tool`, `dismiss`）
  - `evidence`: 参照した素材の短い列挙（天気/ニュース/進捗要約など）。取得していない素材は列挙しない。
- CUI/Webともに同フォーマットで表示。CUIでは`play_audio`可否をuser_preferences.auto_voiceで決定。

### 6) Feedback Tracker
- Web/CUI側で「役立った/普通/不要」「もっと詳しく/後で」を入力可能にし、`proactive_feedback`へ保存。
- フィードバックは次回のTopic Plannerが使う（例: 連続で「不要」ならそのtopicのクールダウンを延長）。

## データモデル案（SQLite）
```sql
CREATE TABLE proactive_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TEXT NOT NULL,
  topic TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  context_summary TEXT,
  executed_commands TEXT, -- JSON array
  response_text TEXT,
  suggestion_hash TEXT,
  error TEXT
);
CREATE INDEX idx_proactive_runs_at ON proactive_runs(run_at DESC);

CREATE TABLE proactive_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES proactive_runs(id) ON DELETE CASCADE,
  rating TEXT NOT NULL,      -- useful/neutral/boring
  action TEXT,               -- accept/defer/dismiss
  comment TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE user_preferences (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  enabled INTEGER NOT NULL DEFAULT 1,
  frequency_profile TEXT NOT NULL,   -- JSON: {morning: 1, noon:1, evening:1}
  topics_enabled TEXT NOT NULL,      -- JSON配列
  tone TEXT NOT NULL DEFAULT 'friendly',
  auto_exec_policy TEXT NOT NULL DEFAULT 'ask', -- ask/allow_safe/deny_all
  auto_voice INTEGER NOT NULL DEFAULT 0,
  topic_sampling TEXT                 -- JSON: {weather:0.8, news:0.4, fun:0.6, agenda:0.9 ...}
);
```

## BASHスクリプト設計（新規）
- `scripts/proactive/get_weather.sh`
  - 入力: `--city <name>`（任意。省略時はconfigのデフォルト都市）
  - 出力: JSON `{ "location": "...", "temp_c": 21, "condition": "...", "source": "..." }`
  - 実装: まずローカルキャッシュ/ファイルを参照、なければAPI（キーはenv）を叩き、標準出力にJSON。ToolExecutorでホワイトリスト。
- `scripts/proactive/get_headlines.sh`
  - 入力: `--limit 5`
  - 出力: JSON配列（タイトル/URL/発行時刻）。既存 `collected_info` を先に参照し、なければ `collect_news.sh --all --limit N` を呼ぶ。
- `scripts/proactive/get_agenda.sh`
  - 入力: `--date YYYY-MM-DD`（省略時は今日）
  - 出力: JSON `{ "todos":[...], "journal_plan":[...], "busy_slots":[...] }`
  - 実装: `data/ai_secretary.db`から未完TODO、ジャーナル予定系メタデータをSQLで取得。
- `scripts/proactive/get_fun_snippets.sh`
  - 入力: `--limit 3`
  - 出力: JSON配列（ジョーク/豆知識/ショート話題）。ローテーション用に`data/proactive_fun.txt`等を持ち、ハッシュで近似重複を避ける。

## フロー例（1サイクル）
1. Trigger Engineが朝9時に起動。user_preferencesで`progress_check`が許可されている（朝は発火確率高め）。
2. Topic Plannerが `progress_check` を選択し、LLMに「今日のTODO進捗 + 天気(80%) + ニュース(40%) + 休憩提案」をプラン生成させる。
3. Context Aggregatorが抽選で選ばれた `get_agenda.sh --date today`, `get_weather.sh` を実行し、`get_headlines.sh` は今回スキップ。
4. Action Executorが必要なBASHをToolExecutor経由で実行し、結果を `executed_commands` に保存。
5. Response Composerがmaterialを統合し、本文/next_actions/evidenceを生成。
6. メッセージがキューに入り、UIがポーリングして表示。feedback入力を待つ。
7. Feedback Trackerが結果を保存し、Topic Plannerの抑制パラメータを更新。

## API/フロント変更
- Backend
  - `GET /api/proactive/status` : user_preferencesとscheduler状態を返す。
  - `POST /api/proactive/config` : preferences更新（frequency/tone/topics/auto_exec_policy/素材抽選率）。
  - `GET /api/proactive/pending` : 既存pending APIを拡張し、evidence/next_actionsを含める。
  - `POST /api/proactive/feedback` : run_idに対する評価を登録。
- Frontend
  - ON/OFFトグル + 頻度スライダー + topicチェックボックス。
  - 提案カードに「実行」「後で」「不要」ボタン（feedback投稿）。
  - Evidenceの省略表示（展開で詳細jsonを確認できるようにする）。

## プロンプト設計（差分）
- system_planner差分: 「BASHで取得可能な素材一覧」を明示し、必要素材を列挙させる。
- system_executor差分: ユーザーへの返答フォーマット（main_text/next_actions/evidence）を指示。
- system_reviewer差分: 冗長性チェックと安全チェック（自動実行可否はauto_exec_policyを見る）。
- テンプレート: 話題カテゴリごとのスタブを `config/proactive_topics/*.yaml` に持ち、ProactivePromptManagerがロード。

## テスト戦略
- Unit: Topic Plannerのカテゴリ選択ロジック、Trigger Engineの抑制/バックオフ、Context Aggregatorの失敗フォールバック。
- Integration: Orchestrator全体をLLMスタブ＋BASHモックでE2E実行し、`proactive_runs`に記録されることを検証。
- CLIシナリオ: `scripts/test_proactive_chat.sh`（新規）で主要topicを擬似実行し、JSON整形とフォーマットを確認。
- Regression: 既存 `tool_audit` と競合しないことを確認するための監査テストを追加。

## 段階的実装プラン
1. スキーマ/設定: `proactive_runs/proactive_feedback/user_preferences` 追加、topics YAMLとprompts差分追加。
2. コア実装: ProactiveOrchestrator（Trigger/TopicPlanner/ContextAggregator/ActionExecutor/Composer/Feedback）を追加し、既存Schedulerと置換。
3. BASH素材: `get_weather.sh`, `get_headlines.sh`, `get_agenda.sh`, `get_fun_snippets.sh` を実装しtool登録。
4. API/UI: status/config/pending/feedbackエンドポイント拡張、フロントのカードUIと設定パネル更新。
5. テスト: Unit + Integration + CLIシナリオ。CUIチャットでの手動検証手順をREADMEに追加。
