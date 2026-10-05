---
name: omeletland-post
description: Omelet Land Tbilisi の Instagram/Facebook/YouTube 自動投稿に、写真や動画（写真アプリ・inbox・チャットに貼られたもの）を足すときに使う。リール作成・写真投稿の追加・投稿予定の確認。
---

# Omelet Land に投稿を足す

最初に `CLAUDE.md`、次に `HANDOFF.md` を読む。手順・置き場所・決まっていないことはそこに書いてある。

要点:
- できあがった動画 → `python3 add_reel.py 動画 --title … --caption caption.txt`
- 撮ったままの動画 → コマ見本で見せ場を決めて `make_reel.render_montage`
- 写真 → リールなら `make_reel.photo_segment` をつないで `render_montage`、写真投稿なら 1080×1350 で `queue.json`
- 最後に `python3 test_logic.py` を通してから commit・push
- 寿司など新しいメニューは、どのアカウントに出すか・名前・値段を本人に確かめてから
