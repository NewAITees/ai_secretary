# Lifelog System

PC活動を自動的に記録し、AIが理解可能な形式のライフログとして蓄積する基盤システム。

## 概要

- **イベント駆動型**の高精度トラッキング
- **SQLite WALモード**による高性能データベース
- **プライバシー・バイ・デザイン**（デフォルトで個人情報を保存しない）
- **SLO監視**による運用品質の保証

## インストール

```bash
cd lifelog-system
uv sync
```

## 使用方法

### バックグラウンド実行（推奨）

```bash
cd lifelog-system

# デーモン起動
./scripts/daemon.sh start

# 状態確認
./scripts/daemon.sh status

# ログ確認
./scripts/daemon.sh logs

# デーモン停止
./scripts/daemon.sh stop

# 再起動
./scripts/daemon.sh restart
```

### フォアグラウンド実行（テスト用）

```bash
# デフォルト設定で実行
./run.sh

# 実行時間を制限（テスト用）
./run.sh --duration 60
```

### データ閲覧（CLIツール）

```bash
# 日別サマリー表示
uv run python -m src.cli_viewer summary
uv run python -m src.cli_viewer summary --date 2025-11-10

# 時間帯別活動状況
uv run python -m src.cli_viewer hourly
uv run python -m src.cli_viewer hourly --date 2025-11-10

# 最近のタイムライン
uv run python -m src.cli_viewer timeline --hours 2

# ヘルスメトリクス
uv run python -m src.cli_viewer health --hours 24
```

### 設定

#### config/config.yaml

- サンプリング間隔
- アイドル判定閾値
- バルク書き込み設定
- SLO目標値

#### config/privacy.yaml

- タイトル原文保存の可否
- 除外プロセスリスト
- センシティブキーワード

## データベース構造

### テーブル

- **apps**: アプリケーションマスタ
- **activity_intervals**: 活動区間（メインデータ）
- **health_snapshots**: ヘルスモニタリング

### ビュー

- **daily_app_usage**: 日別アプリ使用時間
- **hourly_activity**: 時間帯別活動状況

## プライバシー保護

デフォルトで以下の情報は**保存されません**：

- ウィンドウタイトル原文（ハッシュのみ保存）
- ブラウザのフルURL（ドメインのみ保存）
- キー入力内容

## 開発

### テスト実行

```bash
uv run pytest tests/ -v
```

### コードフォーマット

```bash
uv run black src/ tests/
uv run ruff check src/ tests/
```

## ライセンス

MIT

## 今後の拡張

- MCP Server実装（Claude連携）
- Windows API実装（Win32）
- ブラウザ履歴統合
- ローカルLLMによる日次サマリー
