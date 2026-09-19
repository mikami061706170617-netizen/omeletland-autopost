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
state = {"history": list(state.get("history", []))}
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

print("\n" + ("すべて通過しました。" if not fails else "失敗: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
