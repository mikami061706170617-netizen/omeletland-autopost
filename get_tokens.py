#!/usr/bin/env python3
"""Secrets 3つ (IG_USER_ID / FB_PAGE_ID / PAGE_TOKEN) を取り出して GitHub に登録する。
アプリシークレットと短期トークンは画面に表示されない。"""
import getpass
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

APP_ID = "1813931989607153"        # omeletland-autopost
PAGE_ID = "1328661176989188"       # Omelet Land Tbilisi
VERSIONS = ["v23.0", "v22.0", "v21.0", ""]


def api(path, params):
    errors = []
    for v in VERSIONS:
        url = "https://graph.facebook.com/" + (v + "/" if v else "") + path
        try:
            with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            errors.append("%s: %s" % (v or "(no version)", body[:300]))
            if "version" not in body.lower():
                break
        except Exception as e:
            errors.append("%s: %s" % (v or "(no version)", e))
    raise SystemExit("\nGraph API に失敗しました:\n  " + "\n  ".join(errors) +
                     "\n\nトークンが切れている場合は、Graph API エクスプローラで\n"
                     "「Generate Access Token」を押し直して発行し直してください。")


def main():
    print("=" * 56)
    print(" Secrets の取得（画面には何も表示されません）")
    print("=" * 56)
    print("\n① ブラウザの Graph API エクスプローラで、トークン欄の")
    print("   コピーボタンを押してください。")
    short = getpass.getpass("\n   押したら ⌘V で貼り付けて Enter: ").strip()
    print("\n② アプリの設定→ベーシックで「アプリシークレット」の「表示」を押し、")
    print("   コピーしてください。")
    secret = getpass.getpass("\n   ⌘V で貼り付けて Enter: ").strip()
    if not secret or not short:
        raise SystemExit("両方とも必要です。")

    print("\n1/4 長期トークンに交換中…")
    long_tok = api("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": secret,
        "fb_exchange_token": short,
    })["access_token"]

    print("2/4 ページアクセストークンを取得中…")
    page = api(PAGE_ID, {"fields": "name,access_token,instagram_business_account{id,username}",
                         "access_token": long_tok})
    page_token = page["access_token"]
    print("    ページ: %s" % page.get("name"))

    iba = page.get("instagram_business_account") or {}
    ig_id = iba.get("id")
    if not ig_id:
        raise SystemExit("このページに Instagram プロアカウントがリンクされていません。")
    print("    Instagram: @%s (%s)" % (iba.get("username"), ig_id))

    print("3/4 有効期限を確認中…")
    dbg = api("debug_token", {"input_token": page_token,
                              "access_token": "%s|%s" % (APP_ID, secret)}).get("data", {})
    exp = dbg.get("expires_at", 0)
    print("    有効期限: %s" % ("無期限 ✓" if exp in (0, None)
                                else "⚠ 期限つき（アプリシークレットを確認してください）"))

    print("4/4 GitHub Secrets に登録中…")
    ok = True
    for name, value in (("IG_USER_ID", ig_id), ("FB_PAGE_ID", PAGE_ID), ("PAGE_TOKEN", page_token)):
        r = subprocess.run(["gh", "secret", "set", name], input=value.encode(), capture_output=True)
        good = r.returncode == 0
        ok = ok and good
        print("    %s %s%s" % ("✓" if good else "✗", name,
                               "" if good else " — " + r.stderr.decode().strip()))
    print("\n完了しました。" if ok else "\n一部失敗しました。上のメッセージを三上さんに見せてください。")


if __name__ == "__main__":
    sys.exit(main())
