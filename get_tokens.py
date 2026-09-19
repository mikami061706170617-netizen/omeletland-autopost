#!/usr/bin/env python3
"""Secrets 3つを GitHub に登録する。キーボード操作は不要。
クリップボードを見張っていて、ブラウザ側でコピーされた瞬間に自動で進む。"""
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

APP_ID = "1813931989607153"
PAGE_ID = "1328661176989188"
VERSIONS = ["v23.0", "v22.0", "v21.0", ""]
HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")


def clip():
    return subprocess.run(["pbpaste"], capture_output=True).stdout.decode().strip()


def wait_for(label, test, timeout=1800):
    print("     %s を待っています" % label, end="", flush=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = clip()
        if test(v):
            print("  ✓ 受け取りました")
            return v
        print(".", end="", flush=True)
        time.sleep(2)
    print()
    raise SystemExit("✗ %s が %d秒 以内に来ませんでした。もう一度実行してください。" % (label, timeout))


def api(path, params):
    errors = []
    for v in VERSIONS:
        url = "https://graph.facebook.com/" + (v + "/" if v else "") + path
        try:
            with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            errors.append(body[:300])
            if "version" not in body.lower():
                break
        except Exception as e:
            errors.append(str(e))
    raise SystemExit("\n✗ Graph API に失敗しました:\n  " + "\n  ".join(errors))


subprocess.run(["pbcopy"], input=b"")          # まず空にする

print("=" * 62)
print(" Secrets の登録")
print(" このウィンドウは触らなくて大丈夫です。ブラウザ側だけ見ていてください。")
print("=" * 62)
print()

def is_token(v):
    return v.startswith("EAA") and len(v) > 100

def is_secret(v):
    return bool(HEX32.match(v))

short = secret = None
print("ブラウザの赤いボタンを押してください。順番はどちらからでも大丈夫です。\n")
while short is None or secret is None:
    need = []
    if short is None:
        need.append("アクセストークン")
    if secret is None:
        need.append("アプリシークレット")
    got = wait_for(" と ".join(need), lambda v: (short is None and is_token(v)) or (secret is None and is_secret(v)))
    if is_token(got):
        short = got
        print("     → アクセストークン ✓")
    else:
        secret = got
        print("     → アプリシークレット ✓")
    subprocess.run(["pbcopy"], input=b"")
    print()

print("1/4 長期トークンに交換中…")
long_tok = api("oauth/access_token", {
    "grant_type": "fb_exchange_token", "client_id": APP_ID,
    "client_secret": secret, "fb_exchange_token": short})["access_token"]

print("2/4 ページアクセストークンを取得中…")
page = api(PAGE_ID, {"fields": "name,access_token,instagram_business_account{id,username}",
                     "access_token": long_tok})
page_token = page["access_token"]
print("    ページ: %s" % page.get("name"))
iba = page.get("instagram_business_account") or {}
ig_id = iba.get("id")
if not ig_id:
    raise SystemExit("✗ このページに Instagram プロアカウントがリンクされていません。")
print("    Instagram: @%s (%s)" % (iba.get("username"), ig_id))

print("3/4 有効期限を確認中…")
dbg = api("debug_token", {"input_token": page_token,
                          "access_token": "%s|%s" % (APP_ID, secret)}).get("data", {})
exp = dbg.get("expires_at", 0)
print("    %s" % ("無期限 ✓" if exp in (0, None) else "⚠ 期限つきです"))

print("4/4 GitHub Secrets に登録中…")
ok = True
for name, value in (("IG_USER_ID", ig_id), ("FB_PAGE_ID", PAGE_ID), ("PAGE_TOKEN", page_token)):
    r = subprocess.run(["gh", "secret", "set", name], input=value.encode(), capture_output=True)
    good = r.returncode == 0
    ok = ok and good
    print("    %s %s%s" % ("✓" if good else "✗", name, "" if good else " — " + r.stderr.decode().strip()))

subprocess.run(["pbcopy"], input=b"")
print("\n完了しました。Claudeに「おわった」と伝えてください。" if ok
      else "\n一部失敗しました。上の表示をClaudeに見せてください。")
