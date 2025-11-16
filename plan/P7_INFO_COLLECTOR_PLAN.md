# P7情報収集機能 設計ドキュメント

## 概要

ニュース・RSS・検索の統合情報収集機能。DuckDuckGo検索、RSSフィード、ニュースサイトから情報を収集し、Ollama LLMで要約する。

## アーキテクチャ

### データモデル

**共通基底モデル: `CollectedInfo`**
- すべての情報源に共通のフィールド（source_type, title, url, snippet, etc.）
- 特化モデル: `SearchResult`, `RSSEntry`, `NewsArticle`（`Literal`型でsource_type制約）

**要約モデル: `InfoSummary`**
- LLM生成要約を保存
- 参照元`collected_info`のIDリストを保持

### コンポーネント構成

```
src/info_collector/
├── models.py              # データモデル（Pydantic）
├── repository.py          # SQLite CRUD操作
├── config.py              # 外部設定ローダー
├── summarizer.py          # Ollama LLM統合
└── collectors/
    ├── base.py            # BaseCollector抽象クラス
    ├── search_collector.py   # DuckDuckGo（ddgsライブラリ）
    ├── rss_collector.py      # feedparser
    └── news_collector.py     # BeautifulSoup4 + requests
```

### データフロー

1. **収集**: Collector → `List[CollectedInfo]`
2. **保存**: Repository.add_info() → SQLite（重複排除）
3. **取得**: Repository.search_info() → `List[CollectedInfo]`
4. **要約**: Summarizer → Ollama LLM → `InfoSummary`

## データベーススキーマ

```sql
-- 収集情報テーブル
CREATE TABLE collected_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,        -- 'search', 'rss', 'news'
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT,                     -- 本文（取得可能な場合）
    snippet TEXT,                     -- 要約・抜粋
    published_at TEXT,                -- 公開日時
    fetched_at TEXT NOT NULL,         -- 取得日時
    source_name TEXT,                 -- ソース名
    metadata_json TEXT,               -- その他メタデータ（JSON）
    UNIQUE(source_type, url)          -- 重複防止
);

-- 要約テーブル
CREATE TABLE info_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_type TEXT NOT NULL,       -- 'daily', 'topic', 'search'
    title TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    source_info_ids TEXT,             -- JSON配列
    created_at TEXT NOT NULL,
    query TEXT
);
```

## 外部設定ファイル

**テキストベース（コメント・空行スキップ）:**

- `config/info_collector/rss_feeds.txt` - RSS URL一覧
- `config/info_collector/news_sites.txt` - ニュースサイトURL一覧
- `config/info_collector/search_queries.txt` - 定期検索クエリ

## BASHスクリプト インターフェース

**セキュリティ対策:**
- 環境変数経由でパラメータを渡す（インジェクション対策）
- `python - <<'PYTHON'` ヒアドキュメント形式
- ユーザー入力を直接コマンドに埋め込まない

**スクリプト一覧:**
- `scripts/info_collector/search_web.sh` - Web検索
- `scripts/info_collector/collect_rss.sh` - RSS収集
- `scripts/info_collector/collect_news.sh` - ニュース収集
- `scripts/info_collector/generate_summary.sh` - 要約生成

## REST API設計

**エンドポイント:**
- `POST /api/info/search` - Web検索実行・保存
- `POST /api/info/rss/collect` - RSS収集
- `POST /api/info/news/collect` - ニュース収集
- `GET /api/info/list` - 収集済み情報一覧
- `POST /api/info/summary` - 情報要約生成
- `DELETE /api/info/cleanup` - 古い情報削除

**非同期処理:**
- すべてのエンドポイントで`run_in_threadpool()`使用
- ブロッキングI/O（requests, sqlite3）をスレッドプール実行

**エラーハンドリング:**
- HTTPException（400/422）で適切なステータスコード返却
- エラーパスで200を返さない

## Collector層 設計

### BaseCollector

抽象基底クラス。`collect(**kwargs) -> List[CollectedInfo]`メソッドを定義。

### SearchCollector

- **ライブラリ**: `ddgs` (DuckDuckGo公式Python実装)
- **メソッド**: `search(query, limit)`
- **戻り値**: `List[SearchResult]`

### RSSCollector

- **ライブラリ**: `feedparser`
- **メソッド**: `collect(feed_url, max_entries)`, `collect_multiple(feed_urls, max_entries_per_feed)`
- **戻り値**: `List[RSSEntry]`
- **特徴**: 公開日時パース（published_parsed / updated_parsed）

### NewsCollector

- **ライブラリ**: `beautifulsoup4` + `requests`
- **メソッド**: `collect(site_url, max_articles)`, `collect_multiple(site_urls, max_articles_per_site)`
- **戻り値**: `List[NewsArticle]`
- **スクレイピングロジック**: 汎用的（`<article>`, `<h2><a>`, `<h3><a>`）
- **将来拡張**: playwright-mcp統合（JavaScript必須サイト対応）

## Summarizer層 設計

### InfoSummarizer

**メソッド:**
- `summarize_recent(source_type, limit, use_llm)` - 最近の情報を要約
- `summarize_by_query(query, limit, use_llm)` - クエリ検索で抽出して要約

**LLM統合:**
- OllamaClient使用
- プロンプトテンプレート: 最大10件の情報を含む
- フォールバック: LLM失敗時はテンプレートベースの要約を生成

**要約要件:**
- 主なトピック・傾向を3-5点で整理
- 各トピックについて簡潔に説明
- 重要な情報は見出しを付けて強調

## Repository層 設計

### InfoCollectorRepository

**CRUD操作:**
- `add_info(info)` - 情報追加（重複時はNone返却）
- `get_info_by_id(info_id)` - ID取得
- `search_info(source_type, query, start_date, end_date, limit)` - 検索
- `delete_old_info(days)` - 古い情報削除
- `add_summary(summary)` - 要約保存
- `get_summary_by_id(summary_id)` - 要約取得
- `list_summaries(summary_type, limit)` - 要約一覧

**重複排除:**
- `UNIQUE(source_type, url)`制約
- `IntegrityError`ハンドリング

## 定期実行・定期削除

**スケジューラー統合（P4）:**
- 1日1回: `./scripts/info_collector/collect_rss.sh --all`
- 1日1回: `./scripts/info_collector/collect_news.sh --all`
- 1日1回: `DELETE /api/info/cleanup?days=30`（30日以前削除）

## テスト戦略

**ユニットテスト:**
- Repository層: CRUD操作、重複排除、検索、削除
- Collector層: インスタンス化確認（外部API未呼び出し）
- Summarizer層: フォールバック要約生成

**テスト結果:**
- 10テスト全て通過

## セキュリティ考慮事項

1. **BASHインジェクション対策**: 環境変数経由でパラメータ渡し
2. **SQLインジェクション対策**: パラメータ化クエリ使用
3. **XSS対策**: フロントエンドでエスケープ必須
4. **レート制限**: 将来実装（外部API保護）

## パフォーマンス考慮事項

1. **非同期処理**: FastAPIで`run_in_threadpool()`使用
2. **DB最適化**: インデックス作成（source_type, fetched_at, published_at）
3. **キャッシュ**: 将来実装（同一クエリのキャッシュ）

## 今後の拡張

- [ ] playwright-mcp統合（JavaScript必須サイト対応）
- [ ] サイト固有スクレイピングロジック追加
- [ ] キャッシュ機能実装
- [ ] レート制限機能実装
- [ ] フロントエンドUI実装

## 参照ドキュメント

- `plan/TODO.md` - P7タスクリスト・実装完了記録
- `plan/reviews/P7_info_collector_review.md` - レビュー指摘事項
