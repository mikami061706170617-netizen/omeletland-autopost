#!/usr/bin/env python3
"""Instagram の「場所」に使える Facebook の場所ページ ID を探す（find_location.yml から手動で1回動かす）。

結果はログに出すだけ。何も投稿しない・何も書き換えない。標準ライブラリのみ。
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

V = "v21.0"
TOKEN = os.environ.get("PAGE_TOKEN", "")
PAGE = os.environ.get("FB_PAGE_ID", "")
WORDS = ["Japan Food Hub", "Japan Food Hub Tbilisi", "Onimusha", "Onimusha Tbilisi", "Omelet Land"]
FIELDS = "id,name,location,single_line_address,link"


def get(path, **params):
    params["access_token"] = TOKEN
    url = "https://graph.facebook.com/%s/%s?%s" % (V, path, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode("utf-8", "replace")[:300]}


def show(title, res):
    print("\n== " + title)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:2000])


show("自分の Facebook ページ（住所があれば、この ID をそのまま場所に使える）", get(PAGE, fields=FIELDS))
for w in WORDS:
    show("ページ検索: " + w, get("pages/search", q=w, fields=FIELDS))
for w in WORDS[:4]:
    show("場所検索: " + w, get("search", type="place", q=w, center="41.7275,44.7480", distance=3000,
                               fields="id,name,location"))
