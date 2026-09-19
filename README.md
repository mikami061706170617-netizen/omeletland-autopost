# omeletland-autopost

Omelet Land Tbilisi（@omeletland.tbilisi）の毎朝の自動投稿。
GitHub Actions が毎朝 05:00 UTC（＝トビリシ 9:00）に、Meta公式APIで
Instagram と Facebookページへ1件ずつ投稿する。Mac・Chrome・Claude は不要。

## 中身
| ファイル | 役割 |
|---|---|
| `queue.json` | 14件のキャプションと画像の対応（並び順は固定） |
| `state.json` | 投稿履歴。二重投稿の防止と「次の回」の判定に使う |
| `images/d01〜d14.jpg` | 投稿画像（全て 1080×1350 / 4:5 JPEG） |
| `post.py` | 投稿本体（Python標準ライブラリのみ） |
| `get_tokens.py` | Secrets 3つを取り出して `gh secret set` まで実行する |
| `test_logic.py` | 自己検査（投稿はしない） |
| `daily.yml` | 毎朝の実行。**`.github/workflows/daily.yml` に移動すること** |

## Secrets（リポジトリに3つ）
- `IG_USER_ID` … `17841434846215744`
- `FB_PAGE_ID` … `1328661176989188`
- `PAGE_TOKEN` … 無期限のページアクセストークン（`get_tokens.py` が取得）
- 任意 `IG_LOCATION_ID` … 位置情報タグに使うFacebookページID

## リポジトリは Public 必須
Instagram の API は「公開HTTPSの画像URL」しか受け付けないため。
公開されるのは宣伝用の画像とキャプションだけで、トークンは Secrets に入る。

## 使い方
```
python3 test_logic.py                       # 自己検査
gh workflow run daily.yml -f dry_run=true   # 投稿せず中身だけ確認
gh workflow run daily.yml                   # 本番投稿
gh run watch                                # 結果を見る
```

## 仕様
- 次に出すのは **`state.json` の最後の回の次**。14件出し終えたら自動で次の周へ。
- 同じ日に二度走っても二重投稿しない。
- Instagram が失敗した回は履歴に残さない → 翌朝もう一度同じ回を試す。
  Facebook だけ失敗した場合は Instagram の投稿を活かして履歴に残す。
- Graph API の版は v23 → v22 → v21 → 無指定 の順に自動フォールバック。
- `D05`（クーポン）は `expiry: 2026-10-31` を過ぎると自動でスキップ。
  10/30 までに画像とキャプションを差し替えること。
- 手で投稿した日は `state.json` の `history` に1行足す（二重投稿防止）。

## 現在のキュー（次に出るのは D04）
D03 済 → **D04** → D05 → D06 → D07 → D08 → D09 → D10 → D11 → D12 → D13 → D14 → D01 → D02
