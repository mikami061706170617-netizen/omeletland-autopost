#!/usr/bin/env python3
"""inbox/ に置かれた写真を、写真投稿（とリール）にする。make_reel.yml から動く。

  inbox/sushi1.jpg  ＋ inbox/sushi1.txt（キャプション。無ければ汎用の文）
  → images/dNN.jpg（1080×1350）を作り、queue.json の「次に出す位置」に入れる
  → 写真が3枚以上あれば、それをつないだリール（ゆっくり流す・寄る）も作って reels.json に足す
  → inbox の写真と .txt は消す

キャプションの .txt にハッシュタグが無ければ、いつものタグを足す。日本語は入れない（インスタのルール）。
標準ライブラリ＋ffmpeg のみ。
"""
import json
import os
import re
import subprocess
import sys

import make_reel as M

ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, "inbox")
EXT = (".jpg", ".jpeg", ".png", ".webp")
JP = re.compile(r"[぀-ヿ一-鿿]")
DEFAULT = ("Fresh from our counter today 📸\n"
           "Every plate is cooked to order in our kitchen in Saburtalo.\n\n"
           "ყოველი კერძი — შეკვეთისთანავე 🍳\nВсё готовим под заказ 🍳\n\n" + M.CTA)


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def caption(stem):
    path = os.path.join(INBOX, stem + ".txt")
    text = open(path, encoding="utf-8").read().strip() if os.path.exists(path) else DEFAULT
    text = "\n".join(l for l in text.split("\n") if not JP.search(l)).strip()   # インスタに日本語は出さない
    if "#" not in text:
        text += "\n\n" + M.ADDRESS + "\n\n" + M.TAGS
    return text[:2200]


def next_photo_id(queue):
    nums = [int(m.group(1)) for k in queue["posts"] for m in [re.match(r"D(\d+)$", k)] if m]
    return max(nums or [0]) + 1


def main():
    files = sorted(f for f in os.listdir(INBOX) if f.lower().endswith(EXT)) if os.path.isdir(INBOX) else []
    if not files:
        print("inbox/ に新しい写真はありません")
        return 0
    queue, state = load("queue.json"), load("state.json")
    hist = state.get("history", [])
    last = hist[-1]["id"] if hist else None
    at = queue["order"].index(last) + 1 if last in queue["order"] else len(queue["order"])
    made = []
    for k, f in enumerate(files):
        stem = os.path.splitext(f)[0]
        n = next_photo_id(queue)
        pid, rel = "D%02d" % n, "images/d%02d.jpg" % n
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(INBOX, f), "-frames:v", "1",
                        "-vf", "scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350",
                        "-q:v", "3", os.path.join(ROOT, rel)], check=True)
        queue["posts"][pid] = {"id": pid, "title": "%s (inbox)" % stem, "image": rel, "caption": caption(stem)}
        queue["order"].insert(at + k, pid)
        made.append((os.path.join(INBOX, f), stem))
        print("写真投稿にしました: %s ← %s" % (pid, f))
    save("queue.json", queue)

    if len(made) >= 3:                       # 3枚以上ならリールも
        tmp = os.path.join(ROOT, "_reel")
        os.makedirs(tmp, exist_ok=True)
        segs = []
        for k, (path, stem) in enumerate(made[:6]):
            out = os.path.join(tmp, "p%d.mp4" % k)
            if k % 2 == 0:
                segs.append(M.photo_segment(path, out, 3.2, pan=1 if k % 4 == 0 else -1))
            else:
                segs.append(M.photo_segment(path, out, 2.8, frac=0.8, zoom=1.12))
        reels = M.load_reels()
        rid = M.next_id(reels)
        rel = "reels/%s_photos.mp4" % rid
        M.render_montage(segs, os.path.join(ROOT, rel), reveal_index=len(segs) - 1,
                         hook="Fresh from our kitchen", pop="", dish="Omelet Land Tbilisi")
        reels["posts"][rid] = {"id": rid, "title": "Photo reel (inbox): " + ", ".join(s for _, s in made[:6]),
                               "video": rel, "caption": caption(made[0][1])}
        reels["order"].append(rid)
        M.save_reels(reels)
        print("リールも作りました: %s" % rid)
    for path, stem in made:
        os.remove(path)
        txt = os.path.join(INBOX, stem + ".txt")
        if os.path.exists(txt):
            os.remove(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
