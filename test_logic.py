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
N = len(order)
check("14件以上ある", N >= 14, "%d件" % N)
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
# 実際の履歴は日々進むので、シミュレーション開始日（9/20）より前だけを使う
state = {"history": [h for h in state.get("history", []) if h["date"] < "2026-09-20"]}
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

first = seen[:N]
check("初日は D04（シェフの物語）", seen[0] == "D04", seen[0])
check("%d日で一周（重複なし）" % N, len(set(first)) == N, ",".join(first))
check("%d日目で折り返す" % (N + 1), seen[N] == first[0] if len(seen) > N else False,
      seen[N] if len(seen) > N else "-")
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

print("\n[6] リール（reels.json と自動編集）")
import make_reel as M
import post_reel as PR
reels = json.load(open(os.path.join(ROOT, "reels.json"), encoding="utf-8"))
check("reels の order と posts が一致", set(reels["order"]) == set(reels["posts"]))
for rid in reels["order"]:
    r = reels["posts"][rid]
    cap = r["caption"]
    check("%s %s" % (rid, os.path.basename(r["video"])),
          len(cap) <= 2200 and cap.count("#") <= 30 and os.path.exists(os.path.join(ROOT, r["video"])),
          "%d文字 / タグ%d個" % (len(cap), cap.count("#")))
segs, rv, total = M.timeline(0, 40, 26)
check("早送り→スロー→等速の3区間", [s[2] for s in segs] == [M.FAST, M.SLOW, 1.0], str(segs))
check("パカーンの位置がスロー区間の中", abs(rv - (25.2 / M.FAST + 0.8 / M.SLOW)) < 1e-6, "%.2f秒" % rv)
_, _, long_total = M.timeline(0, 150, 140)
check("長い動画でも60秒以内に収める", long_total <= M.MAX_LEN + 0.01, "%.1f秒" % long_total)
_, _, t7 = M.timeline(0, 434, 434 * 0.65)
check("7分の動画でも60秒以内に収める", t7 <= M.MAX_LEN + 0.01, "%.1f秒" % t7)
_, _, t20 = M.timeline(0, 1200, 1100)
check("20分の動画でも60秒以内に収める", t20 <= M.MAX_LEN + 0.01, "%.1f秒" % t20)
cap = M.caption_for("No.01 Classic Omurice", 25)
check("自動キャプションが制限内", len(cap) <= 2200 and cap.count("#") <= 30,
      "%d文字 / タグ%d個" % (len(cap), cap.count("#")))
fake = {"order": ["R1"], "posts": {"R1": {}}}
rid = M.register(fake, "reels/R2_x.mp4", "", None)
check("新しいリールは R2 として末尾に入る", rid == "R2" and fake["order"] == ["R1", "R2"], rid)
o, _ = M.inbox_opts("/nope/omurice_t14.5.mov")
check("ファイル名の _t14.5 を読める", o.get("reveal") == 14.5, str(o))
PR.today_str = lambda: "2026-10-01"
pid, stop = PR.pick(fake, {"reels_history": [{"id": "R1", "date": "2026-09-20"}]})
check("未投稿のリールから順に出る", pid == "R2", pid or stop)

print("\n[7] YouTube（youtube.json と毎日の順番）")
import post_youtube as Y
yq = {"order": ["S1", "L1", "S2"], "posts": {
    "S1": {"id": "S1", "kind": "short", "video": "youtube/S1.mp4", "title": "a", "description": "d"},
    "L1": {"id": "L1", "kind": "long", "video": "youtube/L1.mp4", "title": "b", "description": "d"},
    "S2": {"id": "S2", "kind": "short", "video": "youtube/S2.mp4", "title": "c", "description": "d"}}}
Y.today_str = lambda: "2026-09-26"
st = {"youtube_history": [{"id": "S1", "kind": "short", "date": "2026-09-25"}]}
check("次のショートは S2", (Y.pick(yq, st, "short") or {}).get("id") == "S2")
check("ロングは L1", (Y.pick(yq, st, "long") or {}).get("id") == "L1")
st["youtube_history"].append({"id": "S2", "kind": "short", "date": "2026-09-26"})
check("同じ日に2本目のショートは出さない", Y.pick(yq, st, "short") is None)
if os.path.exists(os.path.join(ROOT, "youtube.json")):
    yj = json.load(open(os.path.join(ROOT, "youtube.json"), encoding="utf-8"))
    for vid in yj["order"]:
        p = yj["posts"][vid]
        ok = (len(p["title"]) <= 100 and len(p["description"]) <= 5000
              and os.path.exists(os.path.join(ROOT, p["video"]))
              and os.path.getsize(os.path.join(ROOT, p["video"])) < 100e6)
        check("%s %s" % (vid, p["video"]), ok, "%d文字" % len(p["title"]))

yq2 = {"order": ["S1"], "posts": {"S1": {"id": "S1", "kind": "short", "video": "v", "reel": "R3"}}}
st2 = {"reels_history": [{"id": "R1"}, {"id": "R3"}, {"id": "R2"}],
       "youtube_history": [{"id": "S1", "kind": "short", "date": "2026-09-25"}]}
Y.load = lambda name, default=None: {"posts": {
    "R1": {"title": "a", "video": "reels/R1.mp4", "no_youtube": True},
    "R2": {"title": "b", "video": "reels/R2.mp4"},
    "R3": {"title": "c", "video": "reels/R3.mp4"}}}
rs = Y.reel_short(yq2, st2)
check("ショートを出し切ったら、インスタのリールを YouTube にも出す（R1は除外・R3は出し済み）",
      (rs or {}).get("id") == "R2", str(rs and rs["id"]))
check("そのタイトルは100字以内で #shorts つき", rs and len(rs["title"]) <= 100 and "#shorts" in rs["title"])
st2["youtube_history"].append({"id": "R2", "kind": "short", "date": "2026-09-26"})
check("出したリールは二度出さない", Y.reel_short(yq2, st2) is None)

import shutil as _sh
import subprocess as _sp
if _sh.which("ffprobe"):
    for d in ("reels", "youtube"):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if f.endswith(".mp4"):
                trc = _sp.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                               "stream=color_transfer", "-of", "csv=p=0", os.path.join(ROOT, d, f)],
                              capture_output=True, text=True).stdout.strip()
                check("%s/%s は SDR（HDRの印なし＝インスタで真っ暗にならない）" % (d, f),
                      trc in ("bt709", "", "unknown"), trc)
                rot = _sp.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                               "stream_side_data=rotation", "-of", "csv=p=0", os.path.join(ROOT, d, f)],
                              capture_output=True, text=True).stdout.strip()
                check("%s/%s は回転の印なし（横倒しにならない）" % (d, f), rot in ("", "0"), rot)

if _sh.which("ffmpeg"):
    import tempfile as _tf
    _d = _tf.mkdtemp()
    _img = os.path.join(_d, "p.jpg")
    _sp.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=orange:s=400x300", "-frames:v", "1", _img], check=True)
    for _k, _kw in enumerate([dict(pan=1), dict(center=(0.7, 0.5), frac=0.8)]):
        _o = os.path.join(_d, "o%d.mp4" % _k)
        M.photo_segment(_img, _o, 1.0, "No.01", **_kw)
        _wh = _sp.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height,color_transfer",
                       "-of", "csv=p=0", _o], capture_output=True, text=True).stdout.strip()
        check("写真から縦動画を作る（%s）" % ("横に流す" if _k == 0 else "寄る"), _wh == "1080,1920,bt709", _wh)
    _sh.rmtree(_d, ignore_errors=True)

if _sh.which("ffmpeg"):
    import add_reel as AR
    _d = _tf.mkdtemp()
    _src, _dst = os.path.join(_d, "in.mov"), os.path.join(_d, "out.mp4")
    _sp.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=1920x1080:d=2",
             "-color_trc", "arib-std-b67", "-pix_fmt", "yuv420p", _src], check=True)
    AR.normalize(_src, _dst)
    _w, _h, _trc, _dur, _au = AR.info(_dst)
    check("できあがった動画を縦1080×1920・SDR・音ありに直す（add_reel）",
          (_w, _h, _trc, _au) == (1080, 1920, "bt709", True), "%dx%d %s 音%s" % (_w, _h, _trc, _au))
    _sh.rmtree(_d, ignore_errors=True)

print("\n[7b] 1日2回の写真と在庫の知らせ")
os.environ["MAX_PER_DAY"] = "2"
P.today_str = lambda: "2026-10-06"
st = {"history": [{"id": "D04", "date": "2026-10-06"}]}
pid2, stop2 = P.pick(queue, st)
check("2回目の投稿は出る（1日2回）", pid2 is not None and pid2 != "D04", str(pid2 or stop2))
st["history"].append({"id": pid2, "date": "2026-10-06"})
check("3回目は出さない", P.pick(queue, st)[0] is None)
os.environ.pop("MAX_PER_DAY")
check("ふだん（設定なし）は1日1回", P.pick(queue, {"history": [{"id": "D04", "date": "2026-10-06"}]})[0] is None)
import stock_check as SC
_rl, _pn = SC.stock({"order": ["R1", "R2", "R3"]}, {"order": ["D1", "D2"]},
                    {"reels_history": [{"id": "R1"}], "history": [{"id": "D1"}]})
check("在庫を数える（出していないリール・写真）", (_rl, _pn) == (["R2", "R3"], ["D2"]), "%s %s" % (_rl, _pn))
check("在庫の知らせの文に残り日数が入る", "2本" in SC.message(_rl, _pn))

_calls = []
def _fake_api(path, params, method="GET"):
    _calls.append(dict(params))
    if path.endswith("/media") and "location_id" in params:
        raise RuntimeError("(#100) Invalid location")
    if path.endswith("/media"):
        return {"id": "c1"}
    if path.endswith("media_publish"):
        return {"id": "m1"}
    return {"status_code": "FINISHED", "permalink": "https://instagram.com/p/x"}
_real_api, P.api = P.api, _fake_api
try:
    _mid = P.post_instagram("ig", "tok", "https://img", "cap", "123")[0]
    check("場所タグが断られても、場所なしで投稿する", _mid == "m1" and "location_id" not in _calls[1], str(_mid))
finally:
    P.api = _real_api

import re as _re
_jp = _re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_bad = [k for f in ("reels.json", "queue.json")
        for k, p in json.load(open(os.path.join(ROOT, f), encoding="utf-8"))["posts"].items() if _jp.search(p["caption"])]
_notag = [k for f in ("reels.json", "queue.json")
          for k, p in json.load(open(os.path.join(ROOT, f), encoding="utf-8"))["posts"].items() if "#" not in p["caption"]]
check("どのキャプションにもハッシュタグがある", not _notag, ",".join(_notag))
check("インスタのキャプションに日本語を入れない", not _bad and not _jp.search(M.caption_for("No.01", 38)), ",".join(_bad))
import datetime as _dt
class _FakeDT(_dt.datetime):
    _t = None
    @classmethod
    def now(cls, tz=None):
        return cls._t
import importlib.util as _ilu
for _name in ("post_reel", "post"):
    _spec = _ilu.spec_from_file_location("_fresh_" + _name, os.path.join(ROOT, _name + ".py"))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)          # ほかの検査で差し替えていない、元の today_str を使う
    _mod.datetime = _FakeDT
    _FakeDT._t = _dt.datetime(2026, 10, 4, 0, 57, tzinfo=_mod.TBILISI)
    check("%s: 夜中に遅れて動いても前の日の分" % _name, _mod.today_str() == "2026-10-03", _mod.today_str())
    _FakeDT._t = _dt.datetime(2026, 10, 4, 19, 37, tzinfo=_mod.TBILISI)
    check("%s: ふだんの時刻はその日の分" % _name, _mod.today_str() == "2026-10-04", _mod.today_str())

import promo as PM
_pr = {"until": "2026-10-31", "marker": "nigiri FREE", "text": "🎁 nigiri FREE"}
_c = "Hook line\n\nBody\n\n#tag"
check("期間中はお知らせが1段落目の後ろに入る", PM.apply(_c, "2026-10-07", _pr) == "Hook line\n\n🎁 nigiri FREE\n\nBody\n\n#tag")
check("期間が過ぎたら入らない", PM.apply(_c, "2026-11-01", _pr) == _c)
check("クーポンの投稿そのものには二重に入れない", PM.apply("x nigiri FREE\n\ny", "2026-10-07", _pr) == "x nigiri FREE\n\ny")
check("2200字を超えるなら入れない", PM.apply("a" * 2195, "2026-10-07", _pr) == "a" * 2195)
_real_promo = PM.load()
for f in ("reels.json", "queue.json"):
    for k, p in json.load(open(os.path.join(ROOT, f), encoding="utf-8"))["posts"].items():
        _out = PM.apply(p["caption"], "2026-10-07", _real_promo)
        if len(_out) > 2200 or _out.count("#") > 30:
            check("%s お知らせ込みでも 2200字・タグ30個以内" % k, False, "%d字" % len(_out))

print("\n[8] 素材置き場（sozai）")
import fetch_link as FL
job = {"url": "sozai", "mode": "batch", "to_main": True, "items": [
    {"segments": [["a.MOV", 0, 5, 1], ["b.MOV", 3, 4, 0.5]]},
    {"type": "youtube", "id": "S9", "segments": [["a.MOV", 6, 9, 1]]}]}
check("使った元動画だけを数える（二重なし）", FL.used_names(job) == ["a.MOV", "b.MOV"], str(FL.used_names(job)))
check("下見ジョブは何も消さない", FL.used_names({"url": "sozai", "mode": "preview"}) == [])
import py_compile
try:
    py_compile.compile(os.path.join(ROOT, "upload_inbox.py"), doraise=True)
    check("upload_inbox.py の文法", True)
except py_compile.PyCompileError as e:
    check("upload_inbox.py の文法", False, str(e))
ign = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
check("送った記録（.sent_ids.txt）はコミットしない", "inbox/.sent_ids.txt" in ign)

print("\n" + ("すべて通過しました。" if not fails else "失敗: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
