#!/usr/bin/env python3
"""自己検査。投稿はしない。 python3 test_logic.py"""
import json
import os
import struct
import sys
from datetime import datetime, timedelta

import post as P

ROOT = os.path.dirname(os.path.abspath(__file__))
fails = []


def check(name, ok, detail=""):
    print(("  OK   " if ok else "  NG   ") + name + (" — " + detail if detail else ""))
    if not ok:
        fails.append(name)


def jpeg_size(path):
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    raise ValueError("JPEGのサイズが読めません: " + path)


queue = json.load(open(os.path.join(ROOT, "queue.json"), encoding="utf-8"))
order, posts = queue["order"], queue["posts"]

print("\n[1] キューの整合性")
check("14件ある", len(order) == 14, "%d件" % len(order))
check("orderとpostsが一致", set(order) == set(posts), "")
check("IDの重複なし", len(set(order)) == len(order))
check("並びが D03 から始まる", order[0] == "D03", order[0])

print("\n[2] キャプションと画像")
for pid in order:
    p = posts[pid]
    cap = p["caption"]
    img = os.path.join(ROOT, p["image"])
    ok = len(cap) <= 2200 and cap.count("#") <= 30 and os.path.exists(img)
    size = jpeg_size(img) if os.path.exists(img) else (0, 0)
    check("%s %s" % (pid, os.path.basename(p["image"])),
          ok and size == (1080, 1350),
          "%d文字 / タグ%d個 / %dx%d" % (len(cap), cap.count("#"), size[0], size[1]))

print("\n[3] 30日連続シミュレーション（二重投稿・折り返し・期限切れ）")
state = json.load(open(os.path.join(ROOT, "state.json"), encoding="utf-8"))
# 実際の履歴は日々進むので、シミュレーション開始日（9/20）より前だけを使う
state = {"history": [h for h in state.get("history", []) if h["date"] < "2026-09-20"]}
seen, days = [], []
base = datetime(2026, 9, 20)
for d in range(30):
    day = base + timedelta(days=d)
    P.today_str = (lambda s: (lambda: s))(day.strftime("%Y-%m-%d"))
    pid, stop = P.pick(queue, state)
    if stop:
        days.append((day.strftime("%m-%d"), "stop"))
        continue
    seen.append(pid)
    days.append((day.strftime("%m-%d"), pid))
    state["history"].append({"id": pid, "date": day.strftime("%Y-%m-%d")})

first14 = seen[:14]
check("初日は D04（シェフの物語）", seen[0] == "D04", seen[0])
check("14日で一周（重複なし）", len(set(first14)) == 14, ",".join(first14))
check("15日目で折り返す", seen[14] == first14[0] if len(seen) > 14 else False,
      seen[14] if len(seen) > 14 else "-")
after_nov = [pid for (d, pid) in days if d >= "11-01" and pid != "stop"]
check("11/1以降 D05 は出ない", "D05" not in after_nov, ",".join(after_nov[:6]))

print("\n[4] 二重投稿ガード")
P.today_str = lambda: "2026-09-20"
st = {"history": [{"id": "D04", "date": "2026-09-20"}]}
pid, stop = P.pick(queue, st)
check("同じ日に二度走っても止まる", pid is None and stop is not None, stop or "")

print("\n[5] Secrets 欠落時のメッセージ")
for k in ("IG_USER_ID", "FB_PAGE_ID", "PAGE_TOKEN", "GITHUB_REPOSITORY", "IMAGE_BASE_URL"):
    os.environ.pop(k, None)
os.environ["IMAGE_BASE_URL"] = "https://raw.githubusercontent.com/x/y/main/"
check("画像URLが組み立てられる",
      P.image_url_for(posts["D04"]).endswith("/images/d04.jpg"),
      P.image_url_for(posts["D04"]))

print("\n[6] リール（reels.json と自動編集）")
import make_reel as M
import post_reel as PR
reels = json.load(open(os.path.join(ROOT, "reels.json"), encoding="utf-8"))
check("reels の order と posts が一致", set(reels["order"]) == set(reels["posts"]))
for rid in reels["order"]:
    r = reels["posts"][rid]
    cap = r["caption"]
    check("%s %s" % (rid, os.path.basename(r["video"])),
          len(cap) <= 2200 and cap.count("#") <= 30 and os.path.exists(os.path.join(ROOT, r["video"])),
          "%d文字 / タグ%d個" % (len(cap), cap.count("#")))
segs, rv, total = M.timeline(0, 40, 26)
check("早送り→スロー→等速の3区間", [s[2] for s in segs] == [M.FAST, M.SLOW, 1.0], str(segs))
check("パカーンの位置がスロー区間の中", abs(rv - (25.2 / M.FAST + 0.8 / M.SLOW)) < 1e-6, "%.2f秒" % rv)
_, _, long_total = M.timeline(0, 150, 140)
check("長い動画でも60秒以内に収める", long_total <= M.MAX_LEN + 0.01, "%.1f秒" % long_total)
_, _, t7 = M.timeline(0, 434, 434 * 0.65)
check("7分の動画でも60秒以内に収める", t7 <= M.MAX_LEN + 0.01, "%.1f秒" % t7)
_, _, t20 = M.timeline(0, 1200, 1100)
check("20分の動画でも60秒以内に収める", t20 <= M.MAX_LEN + 0.01, "%.1f秒" % t20)
cap = M.caption_for("No.01 Classic Omurice", 25)
check("自動キャプションが制限内", len(cap) <= 2200 and cap.count("#") <= 30,
      "%d文字 / タグ%d個" % (len(cap), cap.count("#")))
fake = {"order": ["R1"], "posts": {"R1": {}}}
rid = M.register(fake, "reels/R2_x.mp4", "", None)
check("新しいリールは R2 として末尾に入る", rid == "R2" and fake["order"] == ["R1", "R2"], rid)
o, _ = M.inbox_opts("/nope/omurice_t14.5.mov")
check("ファイル名の _t14.5 を読める", o.get("reveal") == 14.5, str(o))
PR.today_str = lambda: "2026-10-01"
pid, stop = PR.pick(fake, {"reels_history": [{"id": "R1", "date": "2026-09-20"}]})
check("未投稿のリールから順に出る", pid == "R2", pid or stop)

print("\n[7] YouTube（youtube.json と毎日の順番）")
import post_youtube as Y
yq = {"order": ["S1", "L1", "S2"], "posts": {
    "S1": {"id": "S1", "kind": "short", "video": "youtube/S1.mp4", "title": "a", "description": "d"},
    "L1": {"id": "L1", "kind": "long", "video": "youtube/L1.mp4", "title": "b", "description": "d"},
    "S2": {"id": "S2", "kind": "short", "video": "youtube/S2.mp4", "title": "c", "description": "d"}}}
Y.today_str = lambda: "2026-09-26"
st = {"youtube_history": [{"id": "S1", "kind": "short", "date": "2026-09-25"}]}
check("次のショートは S2", (Y.pick(yq, st, "short") or {}).get("id") == "S2")
check("ロングは L1", (Y.pick(yq, st, "long") or {}).get("id") == "L1")
st["youtube_history"].append({"id": "S2", "kind": "short", "date": "2026-09-26"})
check("同じ日に2本目のショートは出さない", Y.pick(yq, st, "short") is None)
if os.path.exists(os.path.join(ROOT, "youtube.json")):
    yj = json.load(open(os.path.join(ROOT, "youtube.json"), encoding="utf-8"))
    for vid in yj["order"]:
        p = yj["posts"][vid]
        ok = (len(p["title"]) <= 100 and len(p["description"]) <= 5000
              and os.path.exists(os.path.join(ROOT, p["video"]))
              and os.path.getsize(os.path.join(ROOT, p["video"])) < 100e6)
        check("%s %s" % (vid, p["video"]), ok, "%d文字" % len(p["title"]))

print("\n" + ("すべて通過しました。" if not fails else "失敗: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
