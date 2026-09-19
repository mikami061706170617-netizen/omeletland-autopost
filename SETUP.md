# セットアップ（1回だけ）

## 済んでいること（2026-09-19 時点）
- Metaアプリ `omeletland-autopost`（アプリID `1813931989607153`）作成済み
- 権限5つが「テスト準備完了」
  `pages_show_list` / `pages_read_engagement` / `pages_manage_posts` /
  `instagram_basic` / `instagram_content_publish`
- Graph API Explorer で**短期ユーザートークンを発行済み**
  （全ページ・全Instagramアカウントにオプトイン）
- FBページID `1328661176989188`（Omelet Land Tbilisi）
- IGユーザーID `17841434846215744`（@omeletland.tbilisi）

## 残り
1. GitHubにリポジトリを作って push（Public）
2. `python3 get_tokens.py`
   - アプリシークレット（アプリの設定→ベーシック→「表示」）
   - 短期ユーザートークン（Graph API Explorer のトークン欄のコピーボタン）
   - → 無期限ページトークンを取得し、そのまま `gh secret set` まで実行
3. `gh workflow run daily.yml -f dry_run=true` で確認
4. `gh workflow run daily.yml` で本番投稿（D04＝シェフの物語）

## つまずいたら
| 症状 | 原因と対処 |
|---|---|
| `me/accounts` が空 | ビジネス経由の権限付与では空になる。ページIDを直接指定すればよい（本スクリプトはそうしている） |
| `instagram_business_account` が無い | IGがプロアカウントでない／FBページと未リンク |
| `(#200) Permissions error` | 権限5つのどれかが欠けている |
| トークンに有効期限が出る | アプリシークレットの貼り間違い |
| Actionsが赤バツ `(#190)` | トークン失効。Explorerで再発行して `get_tokens.py` をやり直す |
| 画像が取得できない | リポジトリがPrivateになっている（Public必須） |
