# P7情報収集機能レビュー (2025-11-15)

## 変更概要
- `src/info_collector`配下に検索/RSS/ニュース収集・要約・リポジトリ層を追加
- FastAPIに`/api/info/*`ルートを追加し、Bashスクリプト（`scripts/info_collector/*.sh`）からも呼び出せるCLIを整備
- `pyproject.toml`へ `feedparser` / `beautifulsoup4` / `ddgs` を追加

## 指摘事項
1. **高: CLIでユーザー入力が無エスケープのままPythonワンライナーへ埋め込まれている**  
   - 該当: `scripts/info_collector/search_web.sh:17-47`, `collect_rss.sh:34-94`, `collect_news.sh:34-94`, `generate_summary.sh:39-68`  
   - 単一引用符埋め込みのまま `'$QUERY'` `'$FEED_URL'` などへ展開しているため、クエリに `'` が入るとSyntaxErrorになる上、任意コード実行も可能。`python - "$@"` でstdin経由にするか、`printf '%q'`等でエスケープを挟む必要がある。  
   - 修正案: `read -r`で受け取り、`python - <<'PY'` として `json.dump`に渡す値を`os.environ`経由で受け取る方式へ変更。

2. **中: FastAPIの非同期ルート内で同期I/Oを直接実行している**  
   - 該当: `src/server/routes/info_collector.py:52-188`  
   - `SearchCollector`/`RSSCollector`/`NewsCollector`は`requests`や`sqlite3`などブロッキングI/Oを使うが、`async def`内で直接呼び出しているためイベントループが停止する。大量アクセス時に他リクエストが詰まる。  
   - 修正案: `from fastapi.concurrency import run_in_threadpool` を使ってコレクター/リポジトリ呼び出しをラップする、もしくは各コレクターを`asyncio.to_thread`で実行する。

3. **中: エラーパスでHTTP 200を返却している**  
   - 該当: `src/server/routes/info_collector.py:82-91`, `111-120`  
   - RSS/ニュース収集で設定値不足や入力不足の場合に `{"error": "..."}`
     を返すだけなので、クライアント側が失敗を検知しづらい。  
   - 修正案: `from fastapi import HTTPException` を使い、400/422等の適切なステータスコードで例外を投げる。

4. **低: コード内で参照している設計ドキュメントが欠落している**  
   - 該当: `src/info_collector/models.py:4`, `repository.py:4`, `config.py:4` などで `plan/P7_INFO_COLLECTOR_PLAN.md` を参照しているが、同ファイルはリポジトリに存在しない。  
   - 修正案: 実際の設計メモを `plan/` 配下に追加するか、コメント内リンクを最新のドキュメントへ更新する。

## 推奨される次のアクション
1. CLIの実行フローをリファクタリングし、全ユーザー入力をPython側へ安全に渡す
2. FastAPIルートをスレッドプール実行に切り替え、HTTPエラーコードの定義を行う
3. 設計ドキュメントの所在を整備し、コメントと実態を一致させる
