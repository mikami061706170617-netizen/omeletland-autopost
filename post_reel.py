#!/usr/bin/env python3
"""Omelet Land Tbilisi — リールの自動投稿（Instagram Reels + Facebookページ動画）。

標準ライブラリのみ。写真の毎朝投稿（post.py）とは独立して動く。
必要な環境変数: IG_USER_ID / FB_PAGE_ID / PAGE_TOKEN
任意: DRY_RUN=true, VIDEO_BASE_URL
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
POLL_SECONDS = 600          # 動画は処理に時間がかかる（最大10分待つ）


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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def api(path, params, method="GET"):
    errors = []
    for v in VERSIONS:
        base = "https://graph.facebook.com/" + (v + "/" if v else "")
        try:
            return _request(base + path, params, method)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            errors.append("%s -> %s %s" % (v or "(no version)", e.code, body[:400]))
            low = body.lower()
            if not ("unsupported get request" in low or "unsupported post request" in low
                    or "unknown path" in low or "version" in low):
                raise RuntimeError(" | ".join(errors))
        except Exception as e:
            errors.append("%s -> %s" % (v or "(no version)", e))
    raise RuntimeError(" | ".join(errors))


def video_urls(post):
    """raw.githubusercontent を第一候補、jsDelivr を予備に使う。"""
    explicit = os.environ.get("VIDEO_BASE_URL")
    if explicit:
        base = explicit if explicit.endswith("/") else explicit + "/"
        return [urllib.parse.urljoin(base, post["video"])]
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        raise RuntimeError("VIDEO_BASE_URL か GITHUB_REPOSITORY が必要です")
    return [
        "https://raw.githubusercontent.com/%s/%s/%s" % (repo, ref, post["video"]),
        "https://cdn.jsdelivr.net/gh/%s@%s/%s" % (repo, ref, post["video"]),
    ]


def pick(reels, state):
    order = reels["order"]
    posted = {h["id"] for h in state.get("reels_history", [])}
    today = today_str()
    if any(h.get("date") == today for h in state.get("reels_history", [])):
        return None, "今日はすでにリールを出しています"
    for pid in order:
        if pid not in posted:
            return pid, None
    return None, "未投稿のリールがありません（新しく撮ったら reels.json に足してください）"


def publish_instagram(ig_user, token, url, caption):
    params = {"media_type": "REELS", "video_url": url, "caption": caption,
              "share_to_feed": "true", "access_token": token}
    loc = os.environ.get("IG_LOCATION_ID")
    if loc:
        params["location_id"] = loc
    container = api("%s/media" % ig_user, params, "POST")["id"]

    waited = 0
    while waited < POLL_SECONDS:
        info = api(container, {"fields": "status_code,status", "access_token": token})
        status = info.get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("IGの動画処理に失敗: %s" % info.get("status"))
        time.sleep(10)
        waited += 10
    else:
        raise RuntimeError("IGの動画処理が%d秒以内に終わりませんでした" % POLL_SECONDS)

    media_id = api("%s/media_publish" % ig_user,
                   {"creation_id": container, "access_token": token}, "POST")["id"]
    permalink = ""
    try:
        permalink = api(media_id, {"fields": "permalink", "access_token": token}).get("permalink", "")
    except Exception:
        pass
    return media_id, permalink


def publish_facebook(page_id, token, url, caption):
    res = api("%s/videos" % page_id,
              {"file_url": url, "description": caption, "access_token": token}, "POST")
    vid = res.get("id", "")
    return vid, ("https://www.facebook.com/%s/videos/%s" % (page_id, vid) if vid else "")


def main():
    dry = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    reels = load_json("reels.json")
    state = load_json("state.json", {"history": []})

    pid, stop = pick(reels, state)
    if stop:
        print("停止: %s" % stop)
        return 0

    post = reels["posts"][pid]
    ig_user = os.environ.get("IG_USER_ID")
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("PAGE_TOKEN")

    missing = [k for k, v in (("IG_USER_ID", ig_user), ("FB_PAGE_ID", page_id),
                              ("PAGE_TOKEN", token)) if not v]
    if missing and not dry:
        print("Secrets が足りません: %s" % ", ".join(missing), file=sys.stderr)
        return 1

    urls = video_urls(post)
    print("今日のリール: %s — %s" % (pid, post["title"]))
    print("動画URL : %s" % urls[0])
    print("文字数  : %d / ハッシュタグ %d 個" % (len(post["caption"]), post["caption"].count("#")))

    if dry:
        print("\n--- DRY RUN: 実際には投稿していません ---")
        print(post["caption"])
        return 0

    ig_id = ig_link = ""
    last_err = None
    for url in urls:
        try:
            ig_id, ig_link = publish_instagram(ig_user, token, url, post["caption"])
            print("Instagram に投稿しました: %s" % (ig_link or ig_id))
            break
        except Exception as e:
            last_err = e
            print("この動画URLでは失敗しました（次を試します）: %s" % e, file=sys.stderr)
    else:
        raise RuntimeError("Instagramへの投稿に失敗しました: %s" % last_err)

    fb_id = fb_link = ""
    try:
        fb_id, fb_link = publish_facebook(page_id, token, urls[0], post["caption"])
        print("Facebook に投稿しました: %s" % (fb_link or fb_id))
    except Exception as e:
        print("Facebook は失敗しました（Instagramは成功）: %s" % e, file=sys.stderr)

    state.setdefault("reels_history", []).append({
        "id": pid, "date": today_str(), "ig": ig_id, "ig_link": ig_link, "fb": fb_id,
    })
    save_state(state)
    print("state.json に記録しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
