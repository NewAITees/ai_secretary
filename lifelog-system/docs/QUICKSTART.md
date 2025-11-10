# Lifelog System - クイックスタートガイド

## 概要

PC活動を自動記録し、ライフログとしてSQLiteデータベースに保存するシステムです。

## 特徴

- ✅ **完全ローカル**: すべてのデータはローカルに保存
- ✅ **プライバシー保護**: デフォルトでタイトル等はハッシュ化
- ✅ **バックグラウンド動作**: デーモンとして常駐可能
- ✅ **CLIツール**: コマンドラインで簡単にデータ確認

---

## インストール

```bash
cd /home/perso/analysis/ai_secretary/lifelog-system
uv sync
```

---

## 基本的な使い方

### 1. デーモンを起動（バックグラウンド実行）

```bash
./scripts/daemon.sh start
```

これでバックグラウンドでデータ収集が開始されます。

### 2. 状態確認

```bash
./scripts/daemon.sh status
```

**出力例:**
```
Lifelog is running (PID: 12345)
Memory usage: 30.5 MB
Last log entry:
2025-11-11 00:00:00,000 - __main__ - INFO - Running indefinitely...
```

### 3. データを確認

#### 今日の活動サマリー

```bash
uv run python -m src.cli_viewer summary
```

**出力例:**
```
=== Daily Summary for 2025-11-11 ===

Process                        Total Time   Active Time  Count
----------------------------------------------------------------------
chrome                         02:15:30     02:10:00     45
vscode                         01:30:15     01:28:00     23
terminal                       00:45:20     00:45:20     12
----------------------------------------------------------------------
TOTAL                          04:31:05     04:23:20
```

#### 最近2時間のタイムライン

```bash
uv run python -m src.cli_viewer timeline --hours 2
```

#### 時間帯別の活動

```bash
uv run python -m src.cli_viewer hourly
```

#### システムヘルス

```bash
uv run python -m src.cli_viewer health
```

### 4. デーモン停止

```bash
./scripts/daemon.sh stop
```

---

## よくある操作

### ログをリアルタイムで確認

```bash
./scripts/daemon.sh logs
```

（Ctrl+C で終了）

### デーモン再起動

```bash
./scripts/daemon.sh restart
```

### 特定日のデータを確認

```bash
# 2025-11-10のサマリー
uv run python -m src.cli_viewer summary --date 2025-11-10

# 2025-11-10の時間帯別活動
uv run python -m src.cli_viewer hourly --date 2025-11-10
```

---

## テスト実行

開発時やバージョンアップ後にテストを実行：

```bash
uv run pytest tests/ -v
```

---

## 設定のカスタマイズ

### サンプリング間隔の変更

`config/config.yaml`:

```yaml
collection:
  sampling_interval: 12  # デフォルト12秒
```

### プライバシー設定

`config/privacy.yaml`:

```yaml
privacy:
  # 除外するプロセス（記録しない）
  exclude_processes:
    - keepass.exe
    - password-manager.exe
```

---

## トラブルシューティング

### デーモンが起動しない

```bash
# ログを確認
tail -n 50 logs/lifelog_daemon.log
```

### データベースが壊れた場合

```bash
# データベースを削除して再作成
rm lifelog.db
./scripts/daemon.sh start
```

### メモリ使用量が多い場合

設定ファイルでキューサイズを縮小：

```yaml
collection:
  bulk_write:
    max_queue_size: 500  # デフォルト1000
```

---

## データベースの場所

```
/home/perso/analysis/ai_secretary/lifelog-system/lifelog.db
```

SQLiteなので、直接クエリも可能：

```bash
sqlite3 lifelog.db "SELECT * FROM apps LIMIT 10;"
```

---

## 次のステップ

- MCP Server実装（Claude連携）
- Webダッシュボード
- 日次レポート自動生成
