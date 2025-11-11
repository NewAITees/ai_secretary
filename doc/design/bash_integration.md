# BASH実行機能のAI秘書統合 - 設計ドキュメント

## 概要

AI秘書（AISecretary）に既存のBASH実行ライブラリ（`bash_executor`）を統合し、LLMがBASHコマンドを安全に実行できるようにする。

## 設計原則

### 統一インターフェース

**外部システムアクセス方針（plan/TODO.mdより）:**
- すべての外部システム連携は **BASHコマンドを通じて実行** する
- AI秘書は `subprocess` 経由でコマンドを呼び出し、標準出力/標準エラー出力を解析する
- 認証情報やAPIキーは環境変数または設定ファイルで管理

### セキュリティ第一

- ホワイトリストベースのコマンド検証（既存のCommandValidatorを活用）
- タイムアウト設定（デフォルト30秒）
- ルートディレクトリ外への移動制限
- すべての実行をログ記録

## アーキテクチャ

### データフロー

```
ユーザー入力
  ↓
AISecretary.chat()
  ↓
OllamaClient → LLM推論
  ↓
JSON応答（bashActions配列を含む）
  ↓
AISecretary._process_bash_actions()
  ↓
CommandExecutor.execute() → BASH実行
  ↓
結果を会話履歴に追加
  ↓
(必要に応じて) 再度LLM呼び出し
  ↓
最終応答を返す
```

### コンポーネント構成

```
AISecretary
├── ollama_client: OllamaClient
├── coeiro_client: COEIROINKClient
├── audio_player: AudioPlayer
├── todo_repository: TodoRepository
└── bash_executor: CommandExecutor  ← 新規追加
```

## JSON応答フォーマット

### 拡張仕様

既存の応答JSON（`text`, `speakerUuid`, `todoActions`など）に`bashActions`フィールドを追加：

```json
{
  "text": "現在のディレクトリを確認しますね。",
  "speakerUuid": "3c37646f-3881-5374-2a83-149267990abc",
  "styleId": 0,
  "speedScale": 1.0,
  "volumeScale": 1.0,
  "pitchScale": 0.0,
  "intonationScale": 1.0,
  "prePhonemeLength": 0.1,
  "postPhonemeLength": 0.1,
  "outputSamplingRate": 24000,
  "prosodyDetail": [],
  "todoActions": [],
  "bashActions": [
    {
      "command": "pwd",
      "reason": "現在のディレクトリを確認するため"
    }
  ]
}
```

### bashActionsフィールド仕様

- **型**: `List[dict]`
- **必須キー**:
  - `command` (str): 実行するBASHコマンド
  - `reason` (str): 実行理由（ログ・監査用）
- **オプションキー**:
  - `timeout` (int): カスタムタイムアウト（秒）
  - `confirm` (bool): ユーザー確認を求めるか（将来拡張用）

## AISecretaryへの統合

### 追加メソッド

#### 1. `_build_bash_instruction() -> str`

**責務**: BASH実行機能のシステムプロンプトを生成

**実装内容**:
- 利用可能なコマンド一覧を取得（ホワイトリストから）
- 応答フォーマット説明
- 使用例
- 制約事項

**返却例**:
```
## BASHコマンド実行機能

ファイル操作、情報取得、外部ツール呼び出しが必要な場合、bashActionsフィールドを使用してください。

### 利用可能なコマンド（抜粋）
- ファイル操作: ls, pwd, cat, head, tail, mkdir, touch
- Git: git status, git log, git diff, git branch
- Python: uv run python, uv run pytest
- 検索: grep, find, rg

### 応答例
{
  "text": "現在のディレクトリを確認します。",
  "bashActions": [
    {"command": "pwd", "reason": "現在のディレクトリを確認"}
  ],
  ...
}

### 制約事項
- 危険なコマンド（rm -rf、chmod 777など）は実行できません
- タイムアウトは30秒です
- ルートディレクトリ外への移動は制限されています
- ホワイトリストに登録されたコマンドのみ実行可能です
```

#### 2. `_process_bash_actions(actions: List[dict]) -> List[dict]`

**責務**: bashActionsを処理し、実行結果を返す

**引数**:
- `actions`: bashActions配列

**返却値**:
- 実行結果の配列 `[{"command": str, "result": dict, "error": Optional[str]}]`

**実装ロジック**:
```python
def _process_bash_actions(self, actions: List[dict]) -> List[dict]:
    results = []
    for action in actions:
        command = action.get("command", "")
        reason = action.get("reason", "")
        timeout = action.get("timeout", None)

        self.logger.info(f"Executing bash command: {command} (reason: {reason})")

        try:
            # タイムアウトのオーバーライド
            if timeout and self.bash_executor:
                original_timeout = self.bash_executor.timeout
                self.bash_executor.timeout = timeout

            result = self.bash_executor.execute(command)

            # タイムアウトを元に戻す
            if timeout and self.bash_executor:
                self.bash_executor.timeout = original_timeout

            results.append({
                "command": command,
                "reason": reason,
                "result": result,
                "error": None
            })

        except Exception as e:
            self.logger.error(f"Bash execution failed: {command} - {e}")
            results.append({
                "command": command,
                "reason": reason,
                "result": None,
                "error": str(e)
            })

    return results
```

#### 3. `chat()` メソッドの拡張

**変更点**:
1. LLM応答から`bashActions`を抽出
2. `_process_bash_actions()`で実行
3. 実行結果を会話履歴に"system"メッセージとして追加
4. （オプション）結果を踏まえて再度LLM呼び出し

**実装フロー**:
```python
def chat(self, user_message: str, proactive: bool = False) -> Dict[str, Any]:
    # ... 既存のロジック ...

    # LLM応答を取得
    response = self.ollama_client.chat(...)

    # bashActionsの処理
    bash_actions = response_data.get("bashActions", [])
    if bash_actions and self.bash_executor:
        bash_results = self._process_bash_actions(bash_actions)

        # 結果を会話履歴に追加
        result_message = self._format_bash_results(bash_results)
        self.conversation_history.append({
            "role": "system",
            "content": f"BASHコマンド実行結果:\n{result_message}"
        })

        # 結果を踏まえて再度LLM呼び出し（オプション）
        if self.config.bash_requery_on_result:
            response = self.ollama_client.chat(...)

    # ... 残りのロジック ...
```

#### 4. `_format_bash_results(results: List[dict]) -> str`

**責務**: BASH実行結果を人間可読な形式に整形

**実装例**:
```python
def _format_bash_results(self, results: List[dict]) -> str:
    formatted = []
    for r in results:
        cmd = r["command"]
        reason = r.get("reason", "")

        if r["error"]:
            formatted.append(f"❌ コマンド: {cmd}\n   理由: {reason}\n   エラー: {r['error']}")
        else:
            result = r["result"]
            formatted.append(
                f"✅ コマンド: {cmd}\n"
                f"   理由: {reason}\n"
                f"   終了コード: {result['exit_code']}\n"
                f"   標準出力:\n{result['stdout']}\n"
                f"   標準エラー出力:\n{result['stderr']}"
            )

    return "\n\n".join(formatted)
```

### 初期化の変更

```python
class AISecretary:
    def __init__(
        self,
        config: Optional[Config] = None,
        ollama_client: Optional[OllamaClient] = None,
        coeiroink_client: Optional[COEIROINKClient] = None,
        audio_player: Optional["AudioPlayer"] = None,
        bash_executor: Optional["CommandExecutor"] = None,  # 新規追加
    ):
        # ... 既存の初期化 ...

        # BashExecutorの初期化
        self.bash_executor: Optional["CommandExecutor"] = bash_executor
        if self.bash_executor is None:
            try:
                from ..bash_executor import create_executor
                self.bash_executor = create_executor()
            except Exception as e:
                self.logger.error(f"BashExecutor初期化失敗: {e}")
                self.bash_executor = None

        # BASH実行ガイダンスを追加
        bash_instruction = self._build_bash_instruction()
        if bash_instruction and self.bash_executor:
            self.conversation_history.append(
                {"role": "system", "content": bash_instruction}
            )
```

## 設定拡張

### config.yaml への追加

```yaml
# BASH実行機能
bash_executor:
  enabled: true
  requery_on_result: false  # 実行後に再度LLM呼び出しするか
  log_commands: true        # コマンド実行をログに記録
  max_actions_per_request: 5  # 1リクエストあたりの最大実行数
```

### Config クラスの拡張

```python
@dataclass
class BashExecutorConfig:
    enabled: bool = True
    requery_on_result: bool = False
    log_commands: bool = True
    max_actions_per_request: int = 5

@dataclass
class Config:
    # ... 既存フィールド ...
    bash_executor: BashExecutorConfig = field(default_factory=BashExecutorConfig)
```

## セキュリティ考慮事項

### 実装済み（bash_executorライブラリ）

1. **ホワイトリストベース検証**: 許可されたコマンドのみ実行
2. **危険パターンのブロック**: コマンドインジェクション防止
3. **ルートディレクトリ制限**: 指定ディレクトリ外への移動を防止
4. **タイムアウト**: 無限ループ防止
5. **ログ記録**: 全コマンド実行を記録

### 追加対策

1. **実行数制限**: 1リクエストあたりの最大実行数を設定
2. **ユーザー確認フロー（将来拡張）**:
   - 特定コマンド実行前にUI経由でユーザー承認を求める
   - `bashActions[].confirm: true` フラグで制御
3. **レート制限**: 短時間での大量実行を防止（将来拡張）

## エラーハンドリング

### エラーケース

| エラー種別 | 例外クラス | 処理 |
|-----------|-----------|------|
| コマンド検証失敗 | `SecurityError` | エラーメッセージを会話履歴に追加、実行スキップ |
| タイムアウト | `TimeoutError` | エラーメッセージを会話履歴に追加、次のコマンドへ |
| 実行エラー | `ExecutionError` | エラーメッセージを会話履歴に追加、次のコマンドへ |
| BashExecutor未初期化 | - | bashActions を無視、ログに警告 |

### エラーメッセージ例

```json
{
  "command": "rm -rf /",
  "reason": "ファイル削除",
  "result": null,
  "error": "SecurityError: コマンドがホワイトリストに登録されていません: rm"
}
```

## テスト戦略

### ユニットテスト (`tests/test_ai_secretary_bash.py`)

1. **`_build_bash_instruction()` テスト**
   - ホワイトリストコマンドが含まれているか
   - フォーマットが正しいか

2. **`_process_bash_actions()` テスト**
   - 正常実行ケース
   - エラーハンドリング（SecurityError, TimeoutError, ExecutionError）
   - 複数コマンド実行

3. **`_format_bash_results()` テスト**
   - 成功結果のフォーマット
   - エラー結果のフォーマット

4. **`chat()` 統合テスト**
   - bashActionsを含むLLM応答の処理
   - 実行結果が会話履歴に追加されるか
   - BashExecutor未初期化時の動作

### モック戦略

```python
@patch("src.bash_executor.CommandExecutor")
def test_bash_actions_execution(mock_executor):
    mock_executor.execute.return_value = {
        "stdout": "/home/user\n",
        "stderr": "",
        "exit_code": "0",
        "cwd": "/home/user"
    }

    secretary = AISecretary(bash_executor=mock_executor)
    # テストロジック
```

### エンドツーエンドテスト

実際のOllama + BashExecutorを使用した統合テスト：
1. 簡単なコマンド実行（`pwd`, `ls`）
2. 複数コマンド実行
3. エラーケース（存在しないコマンド、タイムアウト）

## 使用例

### ケース1: ディレクトリ確認

**ユーザー入力:**
```
現在のディレクトリにあるPythonファイルを教えて
```

**LLM応答（1回目）:**
```json
{
  "text": "確認しますね。",
  "bashActions": [
    {"command": "ls *.py", "reason": "Pythonファイル一覧取得"}
  ],
  "speakerUuid": "...",
  ...
}
```

**BASH実行結果:**
```json
{
  "stdout": "test.py\napp.py\n",
  "stderr": "",
  "exit_code": "0",
  "cwd": "/home/perso/analysis/ai_secretary"
}
```

**会話履歴への追加:**
```
system: BASHコマンド実行結果:
✅ コマンド: ls *.py
   理由: Pythonファイル一覧取得
   終了コード: 0
   標準出力:
test.py
app.py
```

**LLM応答（2回目、requery_on_result=trueの場合）:**
```json
{
  "text": "現在のディレクトリにはtest.pyとapp.pyの2つのPythonファイルがあります。",
  "bashActions": [],
  ...
}
```

### ケース2: Git操作

**ユーザー入力:**
```
最新のGitコミットを教えて
```

**LLM応答:**
```json
{
  "text": "確認します。",
  "bashActions": [
    {"command": "git log -1 --oneline", "reason": "最新コミット取得"}
  ],
  ...
}
```

**BASH実行結果:**
```json
{
  "stdout": "2e50f33 feat: lifelog-systemを追加\n",
  "stderr": "",
  "exit_code": "0",
  "cwd": "/home/perso/analysis/ai_secretary"
}
```

### ケース3: エラーハンドリング

**LLM応答:**
```json
{
  "text": "ファイルを削除します。",
  "bashActions": [
    {"command": "rm -rf /tmp/test", "reason": "ファイル削除"}
  ],
  ...
}
```

**BASH実行結果（エラー）:**
```json
{
  "command": "rm -rf /tmp/test",
  "reason": "ファイル削除",
  "result": null,
  "error": "SecurityError: コマンドがホワイトリストに登録されていません: rm"
}
```

**会話履歴への追加:**
```
system: BASHコマンド実行結果:
❌ コマンド: rm -rf /tmp/test
   理由: ファイル削除
   エラー: SecurityError: コマンドがホワイトリストに登録されていません: rm
```

## パフォーマンス考慮事項

1. **実行時間**: BASHコマンド実行により応答が遅延する可能性
   - 対策: タイムアウト設定（デフォルト30秒）
   - 対策: `requery_on_result=false` でLLM再呼び出しをスキップ

2. **トークン使用量**: 実行結果が会話履歴に追加されるため、トークン数が増加
   - 対策: 標準出力/標準エラー出力を適切に切り詰める（将来拡張）

3. **同時実行**: 複数のbashActionsを並列実行するか
   - 現状: 順次実行
   - 将来拡張: `asyncio`による並列実行

## 今後の拡張

1. **ユーザー確認フロー**
   - UIでコマンド実行前に承認を求める
   - `bashActions[].confirm: true` フラグで制御

2. **コマンド履歴管理**
   - 実行したコマンドの履歴をDB保存
   - 統計情報（よく使われるコマンド、エラー率など）

3. **非同期実行**
   - `asyncio`による並列実行
   - 長時間実行コマンドのバックグラウンド処理

4. **結果キャッシング**
   - 同じコマンドの結果をキャッシュ
   - TTL設定でキャッシュ無効化

5. **プラグインシステム**
   - カスタムコマンドハンドラーの追加
   - ドメイン固有のコマンド（例: `@todo add`, `@search`）

## 関連ドキュメント

- [Bash Executor Library 設計書](bash_executor.md)
- [AI Secretary アーキテクチャ](architecture.md)
- [開発ガイド](../../CLAUDE.md)

## 変更履歴

- 2025-11-11: 初版作成
