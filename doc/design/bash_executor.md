# Bash Executor Library - アーキテクチャ設計書

## 概要

Bash Executor Libraryは、安全にBashコマンドを実行するためのPythonライブラリです。Unix哲学の「一つのことをうまくやる」原則に従い、コマンド実行機能のみを提供します。

## 設計原則

### 責務の分離

**このライブラリが提供する機能:**
- ✅ Bashコマンドの安全な実行
- ✅ ホワイトリストによるコマンド検証
- ✅ 作業ディレクトリの追跡
- ✅ 実行結果の構造化された返却
- ✅ 設定ファイルの読み込み

**エージェント側で実装すべき機能:**
- ❌ LLMとの通信
- ❌ 対話ループ
- ❌ メッセージ履歴管理
- ❌ ユーザー確認プロンプト
- ❌ ツールスキーマの生成と管理

## システムアーキテクチャ

```
src/bash_executor/
├── __init__.py          # エクスポートとファクトリー関数
├── exceptions.py        # カスタム例外定義
├── config_loader.py     # 設定読み込み
├── validator.py         # セキュリティ検証
└── executor.py          # コマンド実行エンジン

config/bash_executor/
├── config.yaml          # メイン設定
└── commands_whitelist.txt  # 許可コマンド

tests/bash_executor/
├── test_config_loader.py
├── test_validator.py
└── test_executor.py
```

## コアコンポーネント

### 1. ConfigLoader (config_loader.py)

**責務:** YAML設定ファイルとホワイトリストの読み込み

**主要メソッド:**
- `get(key: str, default: Any) -> Any`: ドット記法で設定値を取得
- `load_whitelist() -> list[str]`: ホワイトリストを読み込み

**設計ポイント:**
- ドット記法（例: `executor.root_dir`）で階層的な設定にアクセス
- ホワイトリスト読み込み時にコメントと空行を自動除外

### 2. CommandValidator (validator.py)

**責務:** コマンドのセキュリティ検証

**主要メソッド:**
- `validate(command: str) -> None`: コマンドを検証

**検証ロジック:**
1. ブロックパターンチェック（`` ` ``、`$()`など）
2. ホワイトリストチェック（パイプ、&&、||で分割して各コマンドを検証）

**設計ポイント:**
- `shlex.split()`を使用して安全にコマンドをパース
- パースエラーは安全のため即座にブロック
- 正規表現で複数コマンドを分割

### 3. CommandExecutor (executor.py)

**責務:** Bashコマンドの実行と結果の返却

**主要メソッド:**
- `execute(command: str) -> dict[str, str]`: コマンドを実行
- `get_cwd() -> str`: 現在の作業ディレクトリを取得

**実行フロー:**
```
1. CommandValidator.validate()でセキュリティチェック
2. subprocess.run()でコマンド実行
3. cdコマンドを検出した場合、cwdを更新
4. 結果を辞書形式で返却 {stdout, stderr, cwd, exit_code}
```

**セキュリティ機能:**
- ルートディレクトリ外への移動を防止
- タイムアウト設定（デフォルト30秒）
- 全実行コマンドをログに記録

### 4. カスタム例外 (exceptions.py)

```
BashExecutorError (基底)
├── SecurityError
│   ├── CommandNotAllowedError
│   └── BlockedPatternError
├── ExecutionError
│   └── TimeoutError
└── ConfigurationError
```

## データフロー

```
ユーザー
  ↓
create_executor() ファクトリー関数
  ↓
ConfigLoader → YAML設定 + ホワイトリスト読み込み
  ↓
CommandValidator 作成
  ↓
CommandExecutor 作成
  ↓
executor.execute(command)
  ↓
validator.validate() → セキュリティチェック
  ↓
subprocess.run() → コマンド実行
  ↓
{stdout, stderr, cwd, exit_code} を返却
```

## 設定ファイル

### config.yaml

```yaml
executor:
  root_dir: /home/perso/analysis/ai_secretary
  shell: /bin/bash
  timeout: 30

security:
  enable_whitelist: true
  whitelist_file: config/bash_executor/commands_whitelist.txt
  block_patterns:
    - "`"
    - "$("

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### commands_whitelist.txt

基本コマンド、ファイル操作、Git、Python、開発ツールなどを許可。
各行に1コマンド、`#`でコメント。

## 使用例

### 基本的な使用

```python
from bash_executor import create_executor

executor = create_executor()
result = executor.execute("ls -la")
print(result['stdout'])
```

### エージェント統合

```python
class AIAgent:
    def __init__(self):
        self.executor = create_executor()

    def run_command(self, command: str):
        try:
            return self.executor.execute(command)
        except SecurityError as e:
            return {"error": str(e)}
```

## セキュリティ考慮事項

### 実装済み

1. **ホワイトリストベースの検証:** 許可されたコマンドのみ実行
2. **危険なパターンのブロック:** コマンドインジェクション防止
3. **ルートディレクトリ制限:** 指定ディレクトリ外への移動を防止
4. **タイムアウト:** 無限ループ防止
5. **ログ記録:** 全コマンド実行を記録

### 今後の改善案

1. **より厳密なパース:** より高度なコマンドインジェクション検出
2. **権限管理:** ユーザー権限の制限
3. **リソース制限:** CPU/メモリ使用量の制限
4. **監査ログ:** より詳細な実行ログ

## テスト戦略

### テストカバレッジ

- **test_config_loader.py (11テスト):** 設定読み込み、ホワイトリスト読み込み
- **test_validator.py (10テスト):** セキュリティ検証、ブロックパターン、ホワイトリスト
- **test_executor.py (9テスト):** コマンド実行、タイムアウト、ディレクトリ管理

### テスト実行

```bash
uv run pytest tests/bash_executor/ -v
```

全30テストがパス。

## パフォーマンス

- **コマンド実行:** subprocess.run()によるネイティブ実行
- **設定読み込み:** 初回のみ（シングルトンパターン推奨）
- **バリデーション:** 正規表現とset lookupで高速

## 今後の拡張

1. **非同期実行:** asyncioサポート
2. **コマンドキューイング:** 複数コマンドのバッチ実行
3. **結果キャッシング:** 同じコマンドの結果をキャッシュ
4. **プラグインシステム:** カスタムバリデーターの追加

## 関連ドキュメント

- [AI Secretary アーキテクチャ](architecture.md)
- [開発ガイド](../../CLAUDE.md)
- [使用例](../../examples/bash_executor/)

## 変更履歴

- 2025-11-09: 初版作成
