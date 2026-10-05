# 引き継ぎ書 — Omelet Land Tbilisi 自動投稿

別の Claude（Mac の Claude アプリ・Claude Code など）がこのフォルダで続きをするための説明。
最初に `CLAUDE.md` の約束を読むこと。この引き継ぎ書はその次に読む。

## 1. 全体の仕組み（GitHub Actions が毎日勝手に動く）
| 時刻（トビリシ） | 何が出るか | 中身の置き場所 | 動かすもの |
|---|---|---|---|
| 09:00 | Instagram・Facebook に写真 1枚 | `queue.json` ＋ `images/dNN.jpg`（1080×1350） | `daily.yml` → `post.py` |
| 15:00 | YouTube（今は **お知らせ方式**: Issue が届き、本人がスマホで手投稿） | `youtube.json`。出し切ったらインスタのリールを使う | `youtube.yml` → `post_youtube.py` |
| 20:00 | リール＋ストーリーズ＋Facebook 動画 | `reels.json` ＋ `reels/RNN_*.mp4`（1080×1920） | `reel.yml` → `post_reel.py` |

- 出した記録は `state.json`（Actions が書く。手で直すのは本人が手投稿した日を足すときだけ）。
- 写真は `queue.json` の順に一周したら最初に戻る。リールは `reels.json` の順に出して、在庫が無い日は出ない。
- 営業時間は **13:00–22:00**（2026-10-04 に変更済み）。

## 2. いちばん多い仕事: 写真アプリの動画・写真を投稿にする（Mac で）
Mac の Claude なら写真アプリから直接取り出せる。

1. まず最新にする: `git pull origin main`
2. 写真アプリから書き出す（どちらか）
   - 本人に Finder の `inbox/` へドラッグしてもらう（いちばん確実）
   - AppleScript で書き出す（アルバム名や日付で探す）。書き方は `upload_inbox.py` の `album_items()` と `export_one()` を真似る
3. 作る
   - **本人がもう編集した動画** → そのまま: `python3 add_reel.py inbox/動画.mov --title "題" --caption caption.txt`
     （縦1080×1920・SDR・100MB 未満に直して、`reels.json` の最後に足す）
   - **撮ったままの動画** → 見せ場を選んで編集: `make_reel.render_montage([(パス, 開始秒, 終了秒, 速度), ...], 出力, reveal_index=パカーンの区間番号, hook=, pop=, dish=)`
     コマ見本で秒数を確かめてから決める（`fetch_link.py` の `preview()` と同じやり方）。パカーンは機械では見つからない
   - **写真だけ** → `make_reel.photo_segment(写真, 出力, 秒, "料理名 · 30 GEL", pan=1)` を3〜4枚つないで `render_montage` に渡す（`₾` はフォントに無いので `GEL` と書く）
   - **写真の投稿** → 1080×1350 に切り出して `images/dNN.jpg`、`queue.json` に足す（キャプションは同じ料理の既存の投稿を使い回すと名前・値段がずれない）
4. 確かめる: `python3 test_logic.py` がすべて通過すること（動画の向き・SDR・キャプション 2200字/タグ30個・順番）
5. 送る: `git add` → `git commit` → `git push origin main`（Actions がその日の時刻に出す）
6. 元の動画は `inbox/` から消す。**撮影素材はコミットしない**（リポジトリは Public）

## 3. 決まっていないこと・本人に聞くこと
- **寿司（2026-10-05〜）**: 寿司を始めた。今の Omelet Land のアカウントに出すか、寿司用の別アカウントか、まだ決まっていない。
  料理名と値段も、本人から聞く。
- 日本の店（オムライスランド）の自動投稿: アカウント名を聞いている途中（別リポジトリで作る予定）。
- YouTube の全自動: Google の API 審査がまだ。申請文は `docs/youtube_audit.md`。

## 4. 本人について
- 三上恭平さん（トビリシ在住）。日本語・短く・一度に1つずつ説明すると伝わる。
- 「どんどん出して」が基本方針。毎日、写真とリールを切らさないのが目標。
- 実写だけ。AI生成に見えるものは出さないが、加工が強いだけで実写のこともあるので、迷ったら本人に聞く。
