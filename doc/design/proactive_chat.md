# 能動的会話機能 設計ドキュメント

## 概要

AI Secretaryが5分ごとにユーザーに自発的に話しかける機能の設計。

## 要件

1. **定期実行**: 5分ごとにAI側から会話を開始
2. **時刻情報**: 現在時刻をプロンプトに含める
3. **プロンプト多様性**: 外部テンプレートから毎回異なるプロンプトを選択
4. **ON/OFF制御**: GUIから機能の有効/無効を切り替え
5. **拡張性**: プロンプトテンプレートの追加が容易

## アーキテクチャ

### コンポーネント構成

```
┌─────────────────────────────────────────────────┐
│ Frontend (React)                                │
│  - ProactiveChatToggle (ON/OFF スイッチ)        │
│  - PendingMessagePoller (10秒ごとポーリング)   │
└────────────┬────────────────────────────────────┘
             │ HTTP API
┌────────────▼────────────────────────────────────┐
│ Backend (FastAPI)                               │
│  ┌──────────────────────────────────────────┐   │
│  │ API Endpoints                            │   │
│  │  - POST /api/proactive-chat/toggle       │   │
│  │  - GET  /api/proactive-chat/status       │   │
│  │  - GET  /api/proactive-chat/pending      │   │
│  └────┬─────────────────────────────────────┘   │
│       │                                          │
│  ┌────▼────────────────────────────────────┐    │
│  │ ProactiveChatScheduler                  │    │
│  │  - 5分ごとのタスク実行                  │    │
│  │  - ON/OFF状態管理                       │    │
│  │  - メッセージキュー管理                 │    │
│  └────┬─────────────────────────────────────┘   │
│       │                                          │
│  ┌────▼────────────────────────────────────┐    │
│  │ ProactivePromptManager                  │    │
│  │  - テンプレートファイル読み込み        │    │
│  │  - ランダム選択                         │    │
│  │  - 変数置換 (時刻等)                    │    │
│  └────┬─────────────────────────────────────┘   │
│       │                                          │
│  ┌────▼────────────────────────────────────┐    │
│  │ AISecretary                             │    │
│  │  - LLM呼び出し                          │    │
│  │  - 音声合成・再生                       │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Data Storage                                    │
│  - config/proactive_prompts/*.txt               │
│    (テンプレートファイル)                       │
└─────────────────────────────────────────────────┘
```

### データフロー

1. **フロントエンド**: ユーザーがON/OFFトグルを操作
2. **API**: `POST /api/proactive-chat/toggle` で状態変更
3. **スケジューラー**: 5分ごとにタイマー発火（有効時のみ）
4. **プロンプト生成**:
   - 現在時刻取得
   - テンプレートファイルからランダム選択
   - 変数置換（`{current_time}` → `2024-01-01 14:30:00`）
5. **AI会話生成**: AISecretaryでLLM呼び出し
6. **メッセージキュー**: 生成されたメッセージをキューに格納
7. **フロントエンド**: 10秒ごとに `GET /api/proactive-chat/pending` でポーリング
8. **メッセージ表示**: キューからメッセージを取得してチャット画面に表示

## 実装詳細

### 1. ProactiveChatScheduler (`src/ai_secretary/scheduler.py`)

**責務**:
- バックグラウンドスレッドで定期タスクを実行
- ON/OFF状態管理
- 生成されたメッセージのキュー管理

**主要メソッド**:
```python
class ProactiveChatScheduler:
    def __init__(self, secretary: AISecretary, prompt_manager: ProactivePromptManager)
    def start(self) -> None  # スケジューラー開始
    def stop(self) -> None   # スケジューラー停止
    def enable(self) -> None # 能動会話を有効化
    def disable(self) -> None # 能動会話を無効化
    def is_enabled(self) -> bool
    def get_pending_messages(self) -> List[Dict[str, Any]]  # キューからメッセージ取得
    def _run_task(self) -> None  # 定期実行タスク本体（プライベート）
```

**タスク実行ロジック**:
```python
def _run_task(self):
    if not self._enabled:
        return

    # プロンプト生成
    prompt = self.prompt_manager.generate_prompt()

    # AI会話実行
    result = self.secretary.chat(prompt, synthesize_voice=True, play_audio=True)

    # キューに追加
    self._message_queue.append({
        "text": result["voice_plan"]["text"],
        "timestamp": time.time(),
        "details": result
    })
```

### 2. ProactivePromptManager (`src/ai_secretary/prompt_templates.py`)

**責務**:
- テンプレートファイルの読み込み
- ランダム選択
- 変数置換

**主要メソッド**:
```python
class ProactivePromptManager:
    def __init__(self, templates_dir: Path)
    def load_templates(self) -> List[str]  # テンプレートファイル読み込み
    def generate_prompt(self) -> str  # ランダム選択 + 変数置換
```

**テンプレートファイル形式** (`config/proactive_prompts/default.txt`):
```
現在時刻は {current_time} です。ユーザーに天気の話題を振ってください。
現在時刻は {current_time} です。今日のニュースについて話しかけてください。
現在時刻は {current_time} です。休憩を勧めてください。
```

**変数置換**:
- `{current_time}`: `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
- 将来的に追加可能: `{day_of_week}`, `{user_name}` など

### 3. API エンドポイント (`src/server/app.py`)

#### `POST /api/proactive-chat/toggle`
**リクエスト**:
```json
{
  "enabled": true
}
```

**レスポンス**:
```json
{
  "enabled": true,
  "message": "Proactive chat enabled"
}
```

#### `GET /api/proactive-chat/status`
**レスポンス**:
```json
{
  "enabled": true,
  "interval_seconds": 300,
  "pending_count": 2
}
```

#### `GET /api/proactive-chat/pending`
**レスポンス**:
```json
{
  "messages": [
    {
      "text": "こんにちは！現在14時30分です。少し休憩しませんか？",
      "timestamp": 1704096600,
      "details": { ... }
    }
  ]
}
```

### 4. フロントエンド実装

#### トグルスイッチUI
```tsx
<label className="app__checkbox">
  <input
    type="checkbox"
    checked={proactiveChatEnabled}
    onChange={handleToggleProactiveChat}
  />
  AI側から定期的に話しかける
</label>
```

#### ポーリング実装
```tsx
useEffect(() => {
  if (!proactiveChatEnabled) return;

  const interval = setInterval(async () => {
    const response = await fetchPendingMessages();
    if (response.messages.length > 0) {
      setMessages(prev => [...prev, ...response.messages]);
    }
  }, 10000); // 10秒ごと

  return () => clearInterval(interval);
}, [proactiveChatEnabled]);
```

## 拡張性

### プロンプトテンプレートの追加

1. `config/proactive_prompts/` に新しい `.txt` ファイルを追加
2. 自動的に読み込まれてランダム選択対象に含まれる

**例**: `config/proactive_prompts/weather.txt`
```
現在時刻は {current_time} です。今日の天気について話してください。
現在時刻は {current_time} です。明日の天気予報を教えてください。
```

### 変数の追加

`ProactivePromptManager.generate_prompt()` で変数を追加:
```python
def generate_prompt(self) -> str:
    template = random.choice(self.templates)
    now = datetime.now()
    return template.format(
        current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        day_of_week=now.strftime("%A"),  # 新規追加
        user_name="ユーザー様"  # 新規追加
    )
```

### 実行間隔のカスタマイズ

将来的にAPI経由で間隔を変更可能に:
```python
POST /api/proactive-chat/config
{
  "interval_seconds": 600  # 10分に変更
}
```

## セキュリティ・パフォーマンス考慮事項

1. **メッセージキューのサイズ制限**: 最大10件まで保持（古いものから削除）
2. **スレッドセーフ**: `threading.Lock()` でキューへのアクセスを保護
3. **エラーハンドリング**: LLM呼び出し失敗時はログ記録のみ、次回リトライ
4. **リソース管理**: アプリケーション終了時にスレッドを適切に停止

## テスト戦略

1. **ユニットテスト**:
   - `ProactivePromptManager`: テンプレート読み込み、変数置換
   - `ProactiveChatScheduler`: ON/OFF切り替え、キュー操作

2. **統合テスト**:
   - エンドツーエンドフロー（モックAISecretary使用）

3. **手動テスト**:
   - 実際のOllama/COEIROINK環境でのE2Eテスト

## 今後の改善案

1. **通知機能**: ブラウザ通知API統合
2. **WebSocket対応**: ポーリングからリアルタイム通信へ移行
3. **カスタムスケジュール**: 時間帯別の実行間隔設定
4. **コンテキスト連携**: 過去の会話履歴を考慮したプロンプト生成
