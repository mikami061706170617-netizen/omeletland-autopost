#!/usr/bin/env python3
"""Omelet Land Tbilisi — 毎朝の自動投稿 (Instagram + Facebook)。

標準ライブラリのみ。GitHub Actions から実行される。
必要な環境変数: IG_USER_ID / FB_PAGE_ID / PAGE_TOKEN
任意: IG_LOCATION_ID (FacebookページID), DRY_RUN=true, IMAGE_BASE_URL
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
TBILISI = timezone(timedelta(hours=4))
VERSIONS = ["v23.0", "v22.0", "v21.0", ""]


def today_str():
    return datetime.now(TBILISI).strftime("%Y-%m-%d")


def load_json(name, default=None):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path) and default is not None:
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(os.path.join(ROOT, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _request(url, params, method):
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def api(path, params, method="GET"):
    """Graph API 呼び出し。版が廃止されていたら自動で古い版に下がる。"""
    errors = []
    for v in VERSIONS:
        base = "https://graph.facebook.com/" + (v + "/" if v else "")
        try:
            return _request(base + path, params, method)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            errors.append("%s -> %s %s" % (v or "(no version)", e.code, body[:400]))
            low = body.lower()
            retryable = ("unsupported get request" in low or "unsupported post request" in low
                         or "unknown path" in low or "version" in low)
            if not retryable:
                raise RuntimeError(" | ".join(errors))
        except Exception as e:  # ネットワーク等
            errors.append("%s -> %s" % (v or "(no version)", e))
    raise RuntimeError(" | ".join(errors))


def pick(queue, state):
    order = queue["order"]
    posts = queue["posts"]
    history = state.get("history", [])
    today = today_str()

    if any(h.get("date") == today for h in history):
        return None, "今日はすでに投稿済み（二重投稿ガード）"

    if not history:
        start = 0
    else:
        last = history[-1]["id"]
        start = (order.index(last) + 1) if last in order else 0

    for step in range(len(order)):
        pid = order[(start + step) % len(order)]
        expiry = posts[pid].get("expiry")
        if expiry and today > expiry:
            continue
        return pid, None
    return None, "出せる投稿がありません（全件が期限切れ）"


def image_url_for(post):
    base = os.environ.get("IMAGE_BASE_URL")
    if not base:
        repo = os.environ.get("GITHUB_REPOSITORY")
        ref = os.environ.get("GITHUB_REF_NAME", "main")
        if not repo:
            raise RuntimeError("IMAGE_BASE_URL か GITHUB_REPOSITORY が必要です")
        base = "https://raw.githubusercontent.com/%s/%s/" % (repo, ref)
    return urllib.parse.urljoin(base if base.endswith("/") else base + "/", post["image"])


def post_instagram(ig_user, token, img, caption, location_id):
    params = {"image_url": img, "caption": caption, "access_token": token}
    if location_id:
        params["location_id"] = location_id
    container = api("%s/media" % ig_user, params, "POST")["id"]

    for _ in range(30):
        info = api(container, {"fields": "status_code,status", "access_token": token})
        status = info.get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("IGコンテナ作成に失敗: %s" % info.get("status"))
        time.sleep(3)

    published = api("%s/media_publish" % ig_user,
                    {"creation_id": container, "access_token": token}, "POST")
    media_id = published["id"]
    permalink = ""
    try:
        permalink = api(media_id, {"fields": "permalink", "access_token": token}).get("permalink", "")
    except Exception:
        pass
    return media_id, permalink


def post_facebook(page_id, token, img, caption):
    res = api("%s/photos" % page_id,
              {"url": img, "caption": caption, "access_token": token}, "POST")
    post_id = res.get("post_id") or res.get("id")
    return post_id, "https://www.facebook.com/%s" % post_id


def main():
    dry = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    queue = load_json("queue.json")
    state = load_json("state.json", {"history": []})

    pid, stop = pick(queue, state)
    if stop:
        print("停止: %s" % stop)
        return 0

    post = queue["posts"][pid]
    ig_user = os.environ.get("IG_USER_ID")
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("PAGE_TOKEN")
    location_id = os.environ.get("IG_LOCATION_ID") or ""

    missing = [k for k, v in (("IG_USER_ID", ig_user), ("FB_PAGE_ID", page_id),
                              ("PAGE_TOKEN", token)) if not v]
    if missing and not dry:
        print("Secrets が足りません: %s" % ", ".join(missing), file=sys.stderr)
        return 1

    img = image_url_for(post)
    print("今日の回: %s — %s" % (pid, post["title"]))
    print("画像URL : %s" % img)
    print("文字数  : %d / ハッシュタグ %d 個" % (len(post["caption"]), post["caption"].count("#")))

    if dry:
        print("\n--- DRY RUN: 実際には投稿していません ---")
        print(post["caption"])
        return 0

    ig_id, ig_link = post_instagram(ig_user, token, img, post["caption"], location_id)
    print("Instagram 投稿しました: %s" % (ig_link or ig_id))

    fb_id, fb_link = "", ""
    try:
        fb_id, fb_link = post_facebook(page_id, token, img, post["caption"])
        print("Facebook 投稿しました: %s" % fb_link)
    except Exception as e:
        print("Facebook は失敗しました（Instagramは成功）: %s" % e, file=sys.stderr)

    state.setdefault("history", []).append({
        "id": pid,
        "date": today_str(),
        "ig": ig_id,
        "ig_link": ig_link,
        "fb": fb_id,
    })
    save_state(state)
    print("state.json に記録しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
