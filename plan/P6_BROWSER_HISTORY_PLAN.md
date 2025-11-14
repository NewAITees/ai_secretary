# P6実装計画: Braveブラウザ履歴のDB格納

## 概要

BraveブラウザのSQLite履歴データベースから閲覧履歴を取得し、AI Secretaryの統合DBに格納する機能を実装します。

## 技術調査結果

### Brave履歴ファイルの場所

Braveは**Chromiumベース**のため、Chromeと同様のSQLite構造を持ちます。

**Windows環境:**
```
C:\Users\[User]\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\History
```

**WSL2からのアクセス（想定パス）:**
```
/mnt/c/Users/[User]/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History
```

**macOS:**
```
~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History
```

**Linux:**
```
~/.config/BraveSoftware/Brave-Browser/Default/History
```

### データベーススキーマ

Braveの`History`ファイルは**SQLiteデータベース**で、主に2つのテーブルで構成されています。

#### 1. `urls`テーブル（ユニークなURL）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER PRIMARY KEY | URL ID |
| url | LONGVARCHAR | URL文字列 |
| title | LONGVARCHAR | ページタイトル |
| visit_count | INTEGER | 訪問回数 |
| typed_count | INTEGER | 手入力された回数 |
| last_visit_time | INTEGER | 最終訪問時刻（Chromiumタイムスタンプ） |
| hidden | INTEGER | 非表示フラグ |
| favicon_id | INTEGER | ファビコンID |

#### 2. `visits`テーブル（個別訪問記録）

| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | INTEGER PRIMARY KEY | 訪問ID |
| url | INTEGER NOT NULL | urls.id への外部キー |
| visit_time | INTEGER NOT NULL | 訪問時刻（Chromiumタイムスタンプ） |
| from_visit | INTEGER | 前の訪問ID（リンク元） |
| transition | INTEGER | 遷移タイプ（リンク/タイプ入力/等） |
| segment_id | INTEGER | セグメントID |
| is_indexed | BOOLEAN | インデックス済みフラグ |

#### リレーション

`visits.url` → `urls.id` で結合することで、各訪問の詳細情報を取得できます。

### タイムスタンプ変換

Chromiumタイムスタンプは**1601年1月1日 00:00 UTC**からのマイクロ秒です。

**Unixタイムスタンプへの変換:**
```python
unix_timestamp = (chromium_timestamp / 1_000_000) - 11_644_473_600
```

または

```python
from datetime import datetime, timedelta

def chromium_to_datetime(chromium_timestamp):
    epoch_start = datetime(1601, 1, 1)
    delta = timedelta(microseconds=chromium_timestamp)
    return epoch_start + delta
```

### データベースロックの問題と対処法

Braveが**起動中は`History`ファイルがロック**されています。

#### 対処法1: ファイルコピー（推奨）
```python
import shutil
import sqlite3
from pathlib import Path

source = Path("/mnt/c/Users/.../History")
temp_copy = Path("/tmp/brave_history_copy.db")
shutil.copy(source, temp_copy)

conn = sqlite3.connect(temp_copy)
# データ読み取り
conn.close()
temp_copy.unlink()  # 削除
```

#### 対処法2: 読み取り専用モード
```python
import sqlite3

conn = sqlite3.connect('file:History?mode=ro&nolock=1', uri=True)
```

ただし、この方法は環境によっては失敗する可能性があるため、**コピー方式を推奨**します。

---

## 実装設計

### 1. データスキーマ設計（AI Secretary統合DB）

既存の`data/ai_secretary.db`に以下のテーブルを追加します。

```sql
-- ブラウザ履歴テーブル
CREATE TABLE browser_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT,
    visit_time TEXT NOT NULL,              -- ISO 8601形式（YYYY-MM-DD HH:MM:SS）
    visit_count INTEGER DEFAULT 1,
    transition_type INTEGER,               -- 遷移タイプ（0=リンク、1=手入力、等）
    source_browser TEXT DEFAULT 'brave',   -- ブラウザ種別
    imported_at TEXT NOT NULL,             -- インポート日時
    brave_url_id INTEGER,                  -- 元のurls.id（デバッグ用）
    brave_visit_id INTEGER                 -- 元のvisits.id（デバッグ用）
);

CREATE INDEX idx_browser_history_url ON browser_history(url);
CREATE INDEX idx_browser_history_visit_time ON browser_history(visit_time DESC);
CREATE INDEX idx_browser_history_title ON browser_history(title);

-- 重複インポート防止用テーブル
CREATE TABLE browser_import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    record_count INTEGER,
    last_visit_time TEXT,                  -- インポートした最新の訪問時刻
    status TEXT DEFAULT 'success'          -- success/partial/failed
);

CREATE INDEX idx_import_log_source ON browser_import_log(source_path);
```

### 2. BASH実行スクリプト設計

#### `scripts/browser/import_brave_history.sh`

```bash
#!/bin/bash
set -euo pipefail

# 引数解析
BRAVE_PROFILE_PATH=""
OUTPUT_JSON="false"
LIMIT=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile-path)
      BRAVE_PROFILE_PATH="$2"
      shift 2
      ;;
    --json)
      OUTPUT_JSON="true"
      shift
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# 自動検出
if [ -z "$BRAVE_PROFILE_PATH" ]; then
  # WSL2環境での自動検出
  if [ -d "/mnt/c/Users" ]; then
    WINDOWS_USER=$(ls /mnt/c/Users | grep -v "^All Users$\|^Default\|^Public" | head -1)
    BRAVE_PROFILE_PATH="/mnt/c/Users/$WINDOWS_USER/AppData/Local/BraveSoftware/Brave-Browser/User Data/Default"
  else
    # Linux/macOS環境
    BRAVE_PROFILE_PATH="$HOME/.config/BraveSoftware/Brave-Browser/Default"
  fi
fi

HISTORY_FILE="$BRAVE_PROFILE_PATH/History"

if [ ! -f "$HISTORY_FILE" ]; then
  echo "{\"error\": \"History file not found: $HISTORY_FILE\"}" >&2
  exit 1
fi

# 一時コピー作成
TEMP_COPY=$(mktemp)
trap "rm -f $TEMP_COPY" EXIT

cp "$HISTORY_FILE" "$TEMP_COPY"

# SQLiteクエリ実行
LIMIT_CLAUSE=""
if [ -n "$LIMIT" ]; then
  LIMIT_CLAUSE="LIMIT $LIMIT"
fi

# JSON出力
sqlite3 "$TEMP_COPY" <<EOF
.mode json
SELECT
  v.id as visit_id,
  u.id as url_id,
  u.url,
  u.title,
  v.visit_time,
  v.transition,
  u.visit_count
FROM visits v
JOIN urls u ON v.url = u.id
ORDER BY v.visit_time DESC
$LIMIT_CLAUSE;
EOF
```

#### `scripts/browser/init_browser_history_db.sh`

統合DBにbrowser_historyテーブルを作成するスクリプト。

### 3. Python実装

#### `src/browser_history/models.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class BrowserHistoryEntry:
    """ブラウザ履歴エントリ"""
    url: str
    title: Optional[str]
    visit_time: datetime
    visit_count: int = 1
    transition_type: int = 0
    source_browser: str = "brave"
    brave_url_id: Optional[int] = None
    brave_visit_id: Optional[int] = None
    id: Optional[int] = None
    imported_at: Optional[datetime] = None
```

#### `src/browser_history/repository.py`

```python
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import BrowserHistoryEntry

class BrowserHistoryRepository:
    """ブラウザ履歴リポジトリ"""

    def __init__(self, db_path: str = "data/ai_secretary.db"):
        self.db_path = Path(db_path)
        self._ensure_tables()

    def _ensure_tables(self):
        """テーブル作成"""
        # 省略（上記SQL参照）

    def add_entry(self, entry: BrowserHistoryEntry) -> int:
        """履歴エントリを追加"""
        # 実装省略

    def list_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        url_pattern: Optional[str] = None,
        limit: int = 100
    ) -> List[BrowserHistoryEntry]:
        """履歴を取得"""
        # 実装省略

    def search_history(self, query: str, limit: int = 50) -> List[BrowserHistoryEntry]:
        """履歴を検索（URL/タイトル）"""
        # 実装省略
```

#### `src/browser_history/importer.py`

```python
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from .models import BrowserHistoryEntry
from .repository import BrowserHistoryRepository

class BraveHistoryImporter:
    """Brave履歴インポーター"""

    CHROMIUM_EPOCH = datetime(1601, 1, 1)
    UNIX_EPOCH_OFFSET = 11_644_473_600  # seconds

    def __init__(self, repository: Optional[BrowserHistoryRepository] = None):
        self.repository = repository or BrowserHistoryRepository()

    @staticmethod
    def chromium_to_datetime(chromium_timestamp: int) -> datetime:
        """Chromiumタイムスタンプを変換"""
        unix_timestamp = (chromium_timestamp / 1_000_000) - BraveHistoryImporter.UNIX_EPOCH_OFFSET
        return datetime.fromtimestamp(unix_timestamp)

    def find_brave_history_path(self) -> Optional[Path]:
        """Brave履歴ファイルを自動検出"""
        # WSL2環境
        wsl_users = Path("/mnt/c/Users")
        if wsl_users.exists():
            for user_dir in wsl_users.iterdir():
                if user_dir.name in ["All Users", "Default", "Default User", "Public"]:
                    continue
                candidate = user_dir / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/History"
                if candidate.exists():
                    return candidate

        # Linux環境
        linux_path = Path.home() / ".config/BraveSoftware/Brave-Browser/Default/History"
        if linux_path.exists():
            return linux_path

        # macOS環境
        mac_path = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/History"
        if mac_path.exists():
            return mac_path

        return None

    def import_history(
        self,
        brave_history_path: Optional[Path] = None,
        limit: Optional[int] = None,
        since: Optional[datetime] = None
    ) -> int:
        """
        Brave履歴をインポート

        Args:
            brave_history_path: Historyファイルのパス（Noneで自動検出）
            limit: インポート件数上限
            since: この日時以降のみインポート

        Returns:
            インポートした件数
        """
        if brave_history_path is None:
            brave_history_path = self.find_brave_history_path()
            if brave_history_path is None:
                raise FileNotFoundError("Brave History file not found")

        # 一時コピー作成
        temp_copy = Path("/tmp/brave_history_temp.db")
        shutil.copy(brave_history_path, temp_copy)

        try:
            conn = sqlite3.connect(temp_copy)
            cursor = conn.cursor()

            # クエリ構築
            query = """
                SELECT
                    v.id as visit_id,
                    u.id as url_id,
                    u.url,
                    u.title,
                    v.visit_time,
                    v.transition,
                    u.visit_count
                FROM visits v
                JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            # データ変換とインポート
            imported_count = 0
            for row in rows:
                visit_id, url_id, url, title, visit_time, transition, visit_count = row

                # タイムスタンプ変換
                dt = self.chromium_to_datetime(visit_time)

                # since フィルタ
                if since and dt < since:
                    continue

                entry = BrowserHistoryEntry(
                    url=url,
                    title=title,
                    visit_time=dt,
                    visit_count=visit_count,
                    transition_type=transition,
                    brave_url_id=url_id,
                    brave_visit_id=visit_id
                )

                self.repository.add_entry(entry)
                imported_count += 1

            return imported_count

        finally:
            temp_copy.unlink(missing_ok=True)
```

### 4. AISecretary統合

```python
# src/ai_secretary/secretary.py に追加

def get_browser_history(
    self,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> List[dict]:
    """
    ブラウザ履歴を取得

    Args:
        query: 検索クエリ（URL/タイトル）
        start_date: 開始日（YYYY-MM-DD）
        end_date: 終了日（YYYY-MM-DD）
        limit: 取得件数上限

    Returns:
        履歴エントリのリスト
    """
    from src.browser_history import BrowserHistoryRepository

    repo = BrowserHistoryRepository()

    if query:
        entries = repo.search_history(query, limit)
    else:
        entries = repo.list_history(start_date, end_date, limit=limit)

    return [
        {
            "url": e.url,
            "title": e.title,
            "visit_time": e.visit_time.isoformat(),
            "visit_count": e.visit_count
        }
        for e in entries
    ]
```

### 5. REST API設計

```python
# src/server/app.py に追加

from src.browser_history import BraveHistoryImporter, BrowserHistoryRepository

@app.post("/api/browser-history/import")
async def import_browser_history(limit: Optional[int] = None):
    """Brave履歴をインポート"""
    try:
        importer = BraveHistoryImporter()
        count = importer.import_history(limit=limit)
        return {"status": "success", "imported_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/browser-history")
async def get_browser_history(
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
):
    """ブラウザ履歴を取得"""
    secretary = get_secretary()
    history = secretary.get_browser_history(query, start_date, end_date, limit)
    return {"history": history}
```

---

## 実装タスクリスト

### Phase 1: 基本実装（コア機能）
- [ ] `src/browser_history/models.py` 作成（データモデル）
- [ ] `src/browser_history/repository.py` 作成（CRUD操作）
- [ ] `src/browser_history/importer.py` 作成（Brave履歴インポーター）
- [ ] `src/browser_history/__init__.py` 作成（モジュール初期化）
- [ ] `scripts/browser/init_browser_history_db.sh` 作成（DB初期化）
- [ ] `scripts/browser/import_brave_history.sh` 作成（BASH経由インポート）
- [ ] 単体テスト作成（`tests/test_browser_history.py`）

### Phase 2: 統合機能
- [ ] `AISecretary.get_browser_history()` 実装
- [ ] REST APIエンドポイント実装（`/api/browser-history/*`）
- [ ] 統合テスト作成（`tests/test_browser_history_integration.py`）

### Phase 3: 自動化・運用機能
- [ ] 定期インポート機能実装（cronまたはスケジューラ）
- [ ] 重複排除ロジック実装（同じvisit_idは再インポートしない）
- [ ] インポート履歴管理機能（`browser_import_log`テーブル活用）
- [ ] フロントエンドUI実装（履歴閲覧・検索）

### Phase 4: 拡張機能（オプション）
- [ ] 複数プロファイル対応
- [ ] 複数ブラウザ対応（Chrome、Firefox等）
- [ ] フィルタリング機能（特定ドメインのみ/除外）
- [ ] プライバシー保護機能（センシティブURLの除外）

---

## セキュリティ・プライバシー考慮事項

### 1. データ保護
- [ ] センシティブなURL（パスワードリセット、認証トークン等）を自動除外
- [ ] 除外パターン設定ファイル（`config/browser_history_exclude.txt`）
- [ ] ローカルストレージのみ（外部送信なし）

### 2. パーミッション
- [ ] ファイル読み取り権限チェック
- [ ] ユーザー同意フロー（初回インポート時）

### 3. データ保持期間
- [ ] 古い履歴の自動削除ポリシー（デフォルト: 90日）
- [ ] P4（定期削除機能）と統合

---

## テスト戦略

### 単体テスト
- Chromiumタイムスタンプ変換の正確性
- ファイル自動検出ロジック
- Repository CRUD操作
- エラーハンドリング（ファイル不在、ロック等）

### 統合テスト
- Brave Historyの実ファイルからのインポート（テストフィクスチャ使用）
- AISecretaryとの統合
- REST API動作確認

### エッジケース
- 空の履歴ファイル
- 破損したSQLiteファイル
- ブラウザ起動中（ロック状態）
- 巨大な履歴ファイル（100万件以上）

---

## 次のステップ

このプランを元に、以下の順序で実装を進めることを推奨します：

1. **Phase 1**: 基本実装を完了させ、手動でBrave履歴をインポートできる状態にする
2. **テスト**: 単体テスト・統合テストで動作確認
3. **Phase 2**: AISecretaryとREST APIに統合
4. **Phase 3**: 自動化機能を追加
5. **Phase 4**: 必要に応じて拡張機能を追加

まずはPhase 1の完了を目指します。
