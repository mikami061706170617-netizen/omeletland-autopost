#!/usr/bin/env python3
"""投稿の在庫を数えて、少なくなったら GitHub の Issue で本人に知らせる（stock.yml から毎朝）。

- リール: reels.json のうち、まだ出していないもの（1日1本使う）
- 写真  : queue.json のうち、一度も出していないもの（1日2枚使う。出し切ると同じ写真の繰り返しになる）
どちらかが 3日分を切ったら「📸 投稿の在庫が少なくなっています」の Issue を開く（開いていれば何もしない）。
足りるようになったら、その Issue を閉じる。標準ライブラリのみ。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
TITLE = "📸 投稿の在庫が少なくなっています"
DAYS = 3
PHOTOS_PER_DAY = 1
REELS_PER_DAY = 2


def load(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)


def stock(reels, queue, state):
    used_r = {h["id"] for h in state.get("reels_history", [])}
    used_p = {h["id"] for h in state.get("history", [])}
    reels_left = [r for r in reels["order"] if r not in used_r]
    photos_new = [p for p in queue["order"] if p not in used_p]
    return reels_left, photos_new


def message(reels_left, photos_new):
    return "\n".join([
        "毎日の投稿の在庫が少なくなっています。",
        "",
        "| | 残り | 何日分 |",
        "|---|---|---|",
        "| リール（毎日 12:37・19:37） | %d本 | %d日 |" % (len(reels_left), len(reels_left) // REELS_PER_DAY),
        "| まだ出していない写真（毎日 17:45） | %d枚 | %d日 |"
        % (len(photos_new), len(photos_new) // PHOTOS_PER_DAY),
        "",
        "### 送ってほしいもの（スマホで撮ってチャットに貼るだけでOK）",
        "- 🍳 オムライスを焼く所〜パカーンの動画（10〜30秒・縦）",
        "- 🍣 寿司・新メニューの皿の写真（真上と斜め45度・明るい所で）",
        "- 😋 お客さんが一口目を食べる所（顔は映さないか、本人のOKをもらう）",
        "- 🏙 お店の外観・看板・カウンター・トビリシの街",
        "",
        "Claude のチャットに貼るか、Mac で `アップロード.command` を押すと、リールと写真投稿にして順番に入れます。",
        "在庫が戻るとこの Issue は自動で閉じます。",
    ])


def github(method, path, payload=None):
    url = "https://api.github.com/repos/%s/%s" % (os.environ["GITHUB_REPOSITORY"], path)
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def main():
    reels_left, photos_new = stock(load("reels.json"), load("queue.json"), load("state.json"))
    low = len(reels_left) < DAYS * REELS_PER_DAY or len(photos_new) < DAYS * PHOTOS_PER_DAY
    print("リール残り %d本 / まだ出していない写真 %d枚 → %s"
          % (len(reels_left), len(photos_new), "少ない" if low else "足りている"))
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes") or not (os.environ.get("GITHUB_TOKEN") and os.environ.get("GITHUB_REPOSITORY")):
        print(message(reels_left, photos_new) if low else "")
        return 0
    q = urllib.parse.quote('repo:%s is:issue is:open in:title "%s"' % (os.environ["GITHUB_REPOSITORY"], TITLE))
    req = urllib.request.Request("https://api.github.com/search/issues?q=" + q,
                                 headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        open_issues = [i for i in json.loads(r.read())["items"] if i["title"] == TITLE]
    if low and not open_issues:
        res = github("POST", "issues", {"title": TITLE, "body": message(reels_left, photos_new)})
        print("Issue を開きました:", res.get("html_url"))
    elif not low:
        for i in open_issues:
            github("PATCH", "issues/%d" % i["number"], {"state": "closed", "state_reason": "completed"})
            print("在庫が戻ったので Issue #%d を閉じました" % i["number"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
