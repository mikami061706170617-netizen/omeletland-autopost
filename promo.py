#!/usr/bin/env python3
"""期間限定のお知らせ（promo.json）を、投稿するときにキャプションへ足す。標準ライブラリのみ。

- 期間（until まで）だけ、1段落目の後ろに入れる
- すでにお知らせの文が入っている投稿（クーポンの投稿そのもの）には足さない
- 足すと 2200 字を超える投稿には足さない
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
LIMIT = 2200


def load(path=None):
    path = path or os.path.join(ROOT, "promo.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def apply(caption, today, promo=None):
    promo = load() if promo is None else promo
    if not promo or today > promo.get("until", ""):
        return caption
    if promo.get("marker", "").lower() in caption.lower():
        return caption
    head, sep, rest = caption.partition("\n\n")
    out = head + "\n\n" + promo["text"] + ("\n\n" + rest if sep else "")
    return out if len(out) <= LIMIT else caption
