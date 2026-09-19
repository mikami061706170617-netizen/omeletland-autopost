#!/usr/bin/env python3
"""Secrets 3つ (IG_USER_ID / FB_PAGE_ID / PAGE_TOKEN) を取り出して GitHub に登録する。

  python3 get_tokens.py

アプリシークレットと短期トークンは画面に表示されない。取得した無期限ページトークンも
画面には出さず、その場で `gh secret set` に流し込む（手で貼る必要なし）。
"""
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
    raise SystemExit("Graph API に失敗しました:\n  " + "\n  ".join(errors))


def main():
    print("Omelet Land 自動投稿 — Secrets の取得\n")
    app_id = input("アプリID [%s]: " % APP_ID).strip() or APP_ID
    page_id = input("FBページID [%s]: " % PAGE_ID).strip() or PAGE_ID
    secret = getpass.getpass("アプリシークレット (画面に出ません): ").strip()
    short = getpass.getpass("短期ユーザートークン (画面に出ません): ").strip()
    if not secret or not short:
        raise SystemExit("両方とも必要です。")

    print("\n1/4 長期ユーザートークンに交換中…")
    long_tok = api("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": secret,
        "fb_exchange_token": short,
    })["access_token"]

    print("2/4 ページアクセストークンを取得中…")
    page = api(page_id, {"fields": "name,access_token,instagram_business_account{id,username}",
                         "access_token": long_tok})
    page_token = page["access_token"]
    print("     ページ: %s" % page.get("name"))

    iba = page.get("instagram_business_account") or {}
    ig_id = iba.get("id")
    if not ig_id:
        raise SystemExit("このページに Instagram プロアカウントがリンクされていません。"
                         "Instagramアプリ→設定→アカウントの種類とツール でビジネスにし、"
                         "Facebookページとリンクしてください。")
    print("     Instagram: @%s (%s)" % (iba.get("username"), ig_id))

    print("3/4 トークンの有効期限を確認中…")
    dbg = api("debug_token", {"input_token": page_token,
                              "access_token": "%s|%s" % (app_id, secret)}).get("data", {})
    expires = dbg.get("expires_at", 0)
    print("     有効期限: %s" % ("無期限" if expires in (0, None) else
                                 "%s ← 無期限になっていません。アプリシークレットを確認してください" % expires))
    scopes = dbg.get("scopes", [])
    need = {"pages_show_list", "pages_read_engagement", "pages_manage_posts",
            "instagram_basic", "instagram_content_publish"}
    missing = sorted(need - set(scopes))
    if missing:
        print("     ⚠ 足りない権限: %s" % ", ".join(missing))

    values = {"IG_USER_ID": ig_id, "FB_PAGE_ID": page_id, "PAGE_TOKEN": page_token}

    print("\n4/4 GitHub Secrets への登録")
    ans = input("いま gh secret set を実行しますか？ (このフォルダのリポジトリに登録します) [Y/n]: ").strip().lower()
    if ans in ("", "y", "yes"):
        for name, value in values.items():
            r = subprocess.run(["gh", "secret", "set", name], input=value.encode(),
                               capture_output=True)
            ok = r.returncode == 0
            print("  %s %s%s" % ("✓" if ok else "✗", name,
                                 "" if ok else " — " + r.stderr.decode().strip()))
        print("\n確認: gh secret list")
    else:
        print("\n次の3行をこのフォルダで実行してください（値は伏せています）:")
        for name in values:
            print("  gh secret set %s" % name)
        print("\n値が必要な場合は --body で渡せますが、履歴に残るので上の対話実行を推奨します。")


if __name__ == "__main__":
    sys.exit(main())
