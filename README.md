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

## リール（動画）の自動投稿 — 2026-09-20 追加
毎週 **月・水・金 20:00 トビリシ時間**（16:00 UTC）に、未投稿のリールを1本ずつ出す。
写真の毎朝投稿とは独立。未投稿が無くなれば静かに止まる（同じリールは二度出さない）。

| ファイル | 役割 |
|---|---|
| `reels.json` | リールのキュー（order と posts） |
| `reels/*.mp4` | 動画本体（1080×1920・音は焼き込み済み） |
| `post_reel.py` | リール投稿（Instagram Reels + Facebookページ動画） |
| `.github/workflows/reel.yml` | 週3回の実行 |
| `photos/` | 実写・チラシの保管（投稿には未使用） |

### 仕様
- Instagram は `media_type=REELS` で投稿し、`share_to_feed=true` でフィードにも残す。
- 動画は処理に時間がかかるため、完了を最大10分待つ。
- 動画URLは raw.githubusercontent を第一候補、失敗したら jsDelivr で再試行。
- Facebookページには通常の動画投稿として同じ動画とキャプションを出す。
- **音源はInstagramの曲を付けられない**（APIの制約）。動画に焼き込んだ音だけになる。
  流行りの曲を乗せたい回は、スマホのInstagramから手で出すこと。

### リールを足すとき
1. 1080×1920 のmp4を `reels/` に置く（20〜60秒、100MB未満）
2. `reels.json` の `posts` に1件足し、`order` の末尾にIDを足す
3. push すれば次の実行日に出る

### 素材について
撮影素材（`動画/`）はリポジトリに入れない（`.gitignore` 済み・数GBあるため）。
Mac の `~/Downloads/インスタ自動投稿/動画/` にある。
