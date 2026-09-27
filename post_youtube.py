#!/usr/bin/env python3
"""Omelet Land — YouTube（オムライス研究所 三上きょうへい）の毎日投稿。

標準ライブラリのみ。youtube.json の順番どおりに、毎日 Shorts を1本、日曜はロングも1本出す。

モード（環境変数 YT_MODE）:
  notify（既定）… YouTube にはアップしない。GitHub の Issue で「今日出す動画」と
                   コピペ用のタイトル・説明・タグを知らせる → スマホの YouTube アプリから手で投稿。
                   （Google の API 審査に通るまでは、API でアップした動画は非公開に固定されるため）
  auto          … YouTube API で公開アップロードする（審査合格後）。
                   必要: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN
任意: DRY_RUN=true, FORCE_LONG=true（曜日に関係なくロングも出す）
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
TBILISI = timezone(timedelta(hours=4))
LONG_WEEKDAY = 6          # 日曜（Monday=0）


def now():
    return datetime.now(TBILISI)


def today_str():
    return now().strftime("%Y-%m-%d")


def load(name, default=None):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path) and default is not None:
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(os.path.join(ROOT, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def pick(queue, state, kind):
    """その種類で、まだ出していない最初の動画。今日すでに出していれば None。"""
    hist = state.get("youtube_history", [])
    done = {h["id"] for h in hist}
    if any(h.get("date") == today_str() and h.get("kind") == kind for h in hist):
        return None
    for vid in queue.get("order", []):
        p = queue["posts"][vid]
        if p.get("kind") == kind and vid not in done:
            return p
    return None


REEL_DESC = """{hook}
ジョージア・トビリシの日本人オムライス屋の厨房から。最後まで見てね。

━━━━━━━━━━
📍 お店：Omelet Land Tbilisi（Japan Food Hub 内）
ジョージア・トビリシ、サブルタロ地区 / 毎日 11:00–23:00
Instagram：https://www.instagram.com/omeletland.tbilisi/
━━━━━━━━━━
🔔 チャンネル登録で、海外オムライス屋の毎日をお届けします
💬 コメントで「食べたいメニュー」を教えてください。作ります！

#オムライス #半熟 #パカーン
BGM：オリジナル"""
REEL_TITLES = ["とろっと半熟…パカーンの瞬間がたまらない #shorts",
               "この半熟、ずるい。ナイフ一本でとろ〜り #shorts",
               "海外で毎日焼いてます。半熟オムライスの開く瞬間 #shorts",
               "音まで美味しい…ジュワッと半熟オムライス #shorts"]
REEL_TAGS = ["オムライス", "半熟オムライス", "パカーン", "ジョージア", "トビリシ", "海外生活",
             "海外飲食店", "日本人", "料理", "ASMR", "omurice", "tbilisi", "georgia", "shorts"]


def reel_short(queue, state):
    """youtube.json のショートを出し切ったら、インスタに出したリールを YouTube ショートにも出す。
    YouTube 用に作ったショート（"reel" で元のリールを書いてあるもの）と重ならないようにする。"""
    try:
        reels = load("reels.json")
    except (OSError, ValueError):
        return None
    linked = {p.get("reel") for p in queue.get("posts", {}).values()}
    done = {h["id"] for h in state.get("youtube_history", [])}
    on_ig = [h["id"] for h in state.get("reels_history", [])]
    for rid in on_ig:
        p = reels["posts"].get(rid)
        if not p or rid in linked or rid in done or p.get("no_youtube"):
            continue
        return {"id": rid, "kind": "short", "video": p["video"],
                "title": REEL_TITLES[len(done) % len(REEL_TITLES)],
                "description": REEL_DESC.format(hook="ナイフを入れた瞬間、とろ〜り。何度見ても気持ちいい半熟オムライス。"),
                "tags": REEL_TAGS}
    return None


def video_url(post):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    return "https://github.com/%s/raw/%s/%s" % (repo, ref, post["video"])


# ---------------------------------------------------------------- notify（Issue で知らせる）

def github(path, payload):
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/%s" % (os.environ["GITHUB_REPOSITORY"], path),
        data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def issue_body(post):
    kind = "ショート（縦）" if post["kind"] == "short" else "ロング（横）"
    return "\n".join([
        "今日の YouTube（%s）です。スマホで次の順にどうぞ。" % kind, "",
        "1. 下の **動画を保存** を開いて、動画を写真アプリに保存",
        "2. YouTube アプリの「＋」→ 保存した動画を選ぶ",
        "3. タイトル・説明・タグを下からコピペして公開", "",
        "📥 **動画を保存**: " + video_url(post), "",
        "### タイトル", "```", post["title"], "```",
        "### 説明", "```", post["description"], "```",
        "### タグ", "```", ", ".join(post.get("tags", [])), "```", "",
        "投稿したらこの Issue を閉じてください。",
    ])


def notify(post):
    res = github("issues", {"title": "📺 今日のYouTube: " + post["title"],
                            "body": issue_body(post)})
    return res.get("html_url", "")


# ---------------------------------------------------------------- auto（API でアップロード）

def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=60) as r:
        return json.loads(r.read())["access_token"]


def upload(post, token):
    meta = {"snippet": {"title": post["title"][:100], "description": post["description"][:5000],
                        "tags": post.get("tags", []), "categoryId": "26", "defaultLanguage": "ja"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    path = os.path.join(ROOT, post["video"])
    size = os.path.getsize(path)
    init = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(init, timeout=60) as r:
        loc = r.headers["Location"]
    with open(path, "rb") as f:
        req = urllib.request.Request(loc, data=f.read(), method="PUT",
                                     headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    with urllib.request.urlopen(req, timeout=1800) as r:
        vid = json.loads(r.read())["id"]
    return vid, ("https://youtube.com/shorts/%s" if post["kind"] == "short" else "https://youtu.be/%s") % vid


# ---------------------------------------------------------------- main

def main():
    dry = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    mode = os.environ.get("YT_MODE", "notify") or "notify"
    queue = load("youtube.json", {"order": [], "posts": {}})
    state = load("state.json", {"history": []})

    todo = []
    s = pick(queue, state, "short")
    if not s and not any(h.get("date") == today_str() and h.get("kind") == "short"
                         for h in state.get("youtube_history", [])):
        s = reel_short(queue, state)
    if s:
        todo.append(s)
    if now().weekday() == LONG_WEEKDAY or os.environ.get("FORCE_LONG", "").lower() in ("1", "true"):
        lg = pick(queue, state, "long")
        if lg:
            todo.append(lg)
    if not todo:
        print("今日出す YouTube 動画はありません（出し済みか、在庫切れ）")
        return 0

    for post in todo:
        print("%s: %s — %s" % (mode, post["id"], post["title"]))
        if dry:
            print(issue_body(post))
            continue
        if mode == "auto":
            vid, link = upload(post, access_token())
        else:
            vid, link = "", notify(post)
        print("→", link)
        state.setdefault("youtube_history", []).append(
            {"id": post["id"], "kind": post["kind"], "date": today_str(), "mode": mode,
             "youtube": vid, "link": link})
        save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
