#!/usr/bin/env python3
"""Omelet Land Tbilisi — オムライス動画を「美味しそうなリール」に自動編集する。

撮ったままの動画（横でも縦でも）から、投稿用の 1080×1920 mp4 を作り、
reels.json の末尾に登録する。あとは reel.yml が月・水・金に出す。

やること:
  - 1080×1920 に中央切り抜き（ぼかし帯なし）
  - 暖色・彩度・シャープで「美味しそう」に色づけ
  - 焼いている前半は早送り、パカーンの瞬間はスローモーション＋白フラッシュ
  - 実音のジュージューを強調し、BGM・ヒュッ・ポン・キラッの効果音を重ねる
  - 冒頭の一言、パカーンの文字、最後に料理名・価格・店名を入れる

使い方:
  python3 make_reel.py 動画.mov --reveal 14.5 --dish "No.01 Classic Omurice" --price 25
  python3 make_reel.py --inbox      # inbox/ に置いた動画をまとめて処理（Actions用）

--reveal はパカーンと開く瞬間（元動画の秒数）。省略すると動画の 65% の位置。
inbox/ ではファイル名に _t14.5 と入れるか、同名の .json を横に置く
（例: inbox/omurice_t14.5.mov / inbox/omurice.json に {"reveal": 14.5, "dish": "...", "price": 25}）。

標準ライブラリ＋ffmpeg のみ（ffmpeg は GitHub Actions の ubuntu に最初から入っている）。
BGMと効果音はこのスクリプトが自前で合成するので、著作権の心配はない。
"""
import argparse
import array
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, "inbox")
VIDEO_EXT = (".mov", ".mp4", ".m4v")
W, H, FPS, SR = 1080, 1920, 30, 48000

FAST = 1.6          # 焼いている前半の早送り倍率
SLOW = 0.5          # パカーンの瞬間のスロー倍率
PRE, POST = 0.8, 1.2  # パカーンの前後何秒をスローにするか（元動画の秒）
MAX_LEN = 58.0      # ストーリーズ（60秒まで）にもそのまま出せる長さ
TAIL_MAX = 10.0     # パカーンの後に残す長さ（元動画の秒）
FAST_MAX = 12.0     # 長い動画はここまで早送り（タイムラプス風）

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",       # Mac
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",    # Ubuntu (Actions)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

ADDRESS = ("Japan Food Hub, 1 Davit Gamrekeli St (corner of Bakhtrioni St), Saburtalo\n"
           "6 min from Technical University metro · Open daily 11:00–23:00")
TAGS = ("#omurice #tbilisi #tbilisifood #tbilisirestaurants #tbilisieats #saburtalo "
        "#japanesefoodtbilisi #georgia #თბილისი #საბურთალო #ომურაისი #オムライス #トビリシ "
        "#foodasmr #satisfying")


# ---------------------------------------------------------------- 時間割

def timeline(start, end, reveal):
    """元動画の [start, end] を 早送り→スロー→等速 の3区間に分ける。

    返り値: ([(区間開始, 区間終了, 速度), ...], 出力側のパカーン秒, 出力の長さ)
    """
    if end - start < 3:
        raise ValueError("動画が短すぎます（3秒以上必要）")
    reveal = min(max(reveal, start), end)
    a0, a1 = start, max(start, reveal - PRE)
    b1 = min(end, reveal + POST)
    end = min(end, b1 + TAIL_MAX)   # 盛り付け後が長い動画は切る
    c_len = end - b1
    slow_len = (b1 - a1) / SLOW

    fast = FAST
    if (a1 - a0) / fast + slow_len + c_len > MAX_LEN and a1 > a0:
        room = MAX_LEN - slow_len - c_len
        fast = min(FAST_MAX, (a1 - a0) / room) if room > 0 else FAST_MAX
    if (a1 - a0) / fast + slow_len + c_len > MAX_LEN:
        # 12倍でも収まらないほど長い動画は、パカーンに近い後半だけ使う
        a0 = a1 - (MAX_LEN - slow_len - c_len) * fast

    segs = [s for s in [(a0, a1, fast), (a1, b1, SLOW), (b1, end, 1.0)] if s[1] - s[0] > 0.05]
    out_reveal = (a1 - a0) / fast + (reveal - a1) / SLOW
    total = sum((e - s) / sp for s, e, sp in segs)
    return segs, out_reveal, total


# ---------------------------------------------------------------- 音（BGMと効果音を合成）

def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


# Fmaj7 → Em7 → Dm7 → Cmaj7（明るくて少し甘い進行）
CHORDS = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]
BEAT = 0.6  # 100 BPM


def synth_bed(total, reveal, sizzle_until=0.0):
    """BGM＋効果音をモノラルfloat配列で返す（-1〜1）。

    sizzle_until > 0 のときは 0〜その秒まで焼き音（ジュージュー）も合成する
    （写真から作るときは実音が無いため）。
    """
    n = int(total * SR)
    buf = array.array("f", bytes(4 * n))
    rnd = random.Random(7)
    two_pi = 2 * math.pi

    def add(t0, dur, fn):
        i0 = max(0, int(t0 * SR))
        i1 = min(n, int((t0 + dur) * SR))
        for i in range(i0, i1):
            buf[i] += fn(i / SR - t0)

    # --- BGM: 1コード = 4拍 ---
    bar = 4 * BEAT
    t = 0.0
    k = 0
    while t < total:
        chord = CHORDS[k % len(CHORDS)]
        # パッド（ゆっくり立ち上がる和音）
        freqs = [_hz(m) for m in chord]
        add(t, bar, lambda x, f=freqs: 0.035 * min(1, x / 0.3) * min(1, (bar - x) / 0.3)
            * sum(math.sin(two_pi * q * x) + 0.5 * math.sin(two_pi * q * 1.003 * x) for q in f))
        # ベース（1拍目と3拍目）
        for b in (0, 2):
            q = _hz(chord[0] - 12)
            add(t + b * BEAT, BEAT * 1.8,
                lambda x, q=q: 0.16 * math.exp(-2.5 * x) * math.sin(two_pi * q * x))
        # アルペジオ（8分音符、1オクターブ上、オルゴール風）
        for s in range(8):
            q = _hz(chord[[0, 1, 2, 3, 2, 3, 1, 2][s]] + 12)
            add(t + s * BEAT / 2, 0.5,
                lambda x, q=q: 0.07 * math.exp(-7 * x)
                * (math.sin(two_pi * q * x) + 0.25 * math.sin(two_pi * 2 * q * x)))
        # 裏拍のシャカ（軽いノイズ）
        for b in range(4):
            add(t + b * BEAT + BEAT / 2, 0.06,
                lambda x: 0.03 * math.exp(-60 * x) * (rnd.random() * 2 - 1))
        t += bar
        k += 1

    # パカーン直前は一瞬BGMを引いて「溜め」を作る
    for i in range(n):
        x = i / SR
        if reveal - 0.5 <= x < reveal:
            buf[i] *= 0.25
    # 最初と最後はフェード
    fi, fo = int(0.4 * SR), int(1.5 * SR)
    for i in range(min(fi, n)):
        buf[i] *= i / fi
    for i in range(min(fo, n)):
        buf[n - 1 - i] *= i / fo

    # --- 効果音 ---
    # ヒュッ（開く直前の風切り音）
    state = [0.0]

    def whoosh(x, d=0.45):
        a = two_pi * (400 + 5000 * (x / d)) / SR
        alpha = a / (a + 1)
        state[0] += alpha * ((rnd.random() * 2 - 1) - state[0])
        return 0.5 * (x / d) ** 2 * state[0]

    add(reveal - 0.45, 0.45, whoosh)
    # ポン（開いた瞬間）
    add(reveal, 0.18, lambda x: 0.55 * math.exp(-28 * x)
        * math.sin(two_pi * (520 * x - 900 * x * x)))
    # キラッ（とろとろが見えたところ）
    for j, m in enumerate((96, 100, 103, 108)):
        q = _hz(m)
        add(reveal + 0.08 + j * 0.06, 1.2,
            lambda x, q=q: 0.06 * math.exp(-5 * x) * math.sin(two_pi * q * x))

    # ジュージュー（高域ノイズ＋ときどきパチッ）
    if sizzle_until > 0:
        prev = 0.0
        crackle = 0.0
        for i in range(min(n, int(sizzle_until * SR))):
            x = i / SR
            env = min(1, x / 0.3) * min(1, (sizzle_until - x) / 0.4)
            w = rnd.random() * 2 - 1
            hp, prev = w - prev, w
            if rnd.random() < 0.0006:
                crackle = 0.5 * (rnd.random() + 0.3)
            crackle *= 0.992
            buf[i] += env * (0.045 * hp + crackle * (rnd.random() * 2 - 1))

    peak = max(1e-9, max(abs(v) for v in buf))
    if peak > 0.95:
        for i in range(n):
            buf[i] *= 0.95 / peak
    return buf


def write_wav(path, samples):
    import wave
    pcm = array.array("h", (int(max(-1, min(1, v)) * 32767) for v in samples))
    if sys.byteorder == "big":
        pcm.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- 映像

def probe(src):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
         "-of", "json", src], capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    return float(info["format"]["duration"]), has_audio


def find_font():
    for f in FONTS:
        if os.path.exists(f):
            return f
    return None


def _text(tmp, name, text, font, size, y, t0, t1, color="white"):
    """drawtext 1個分。文字はファイル経由で渡す（記号のエスケープ事故を防ぐ）。"""
    # 横幅に収まるよう文字サイズを自動で下げる（太字の平均字幅 ≒ 0.72×サイズ。大文字は広いので余裕をみる）
    size = max(28, min(size, int(W * 0.88 / (0.72 * max(1, len(text))))))
    path = os.path.join(tmp, name + ".txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return ("drawtext=fontfile='{font}':textfile='{path}':fontsize={size}:fontcolor={color}"
            ":box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y={y}"
            ":enable='between(t,{t0:.2f},{t1:.2f})'").format(
                font=font, path=path, size=size, color=color, y=y, t0=t0, t1=t1)


def look_chain(reveal, total, texts, tmp, font, crop=True, sharp=0.7):
    """色づけ・フラッシュ・文字入れ（動画でも写真でも共通）。"""
    look = []
    if crop:
        look += ["scale=%d:%d:force_original_aspect_ratio=increase" % (W, H), "crop=%d:%d" % (W, H)]
    look += [
        # 暖色・彩度・コントラストで「焼きたて」の色に
        "eq=contrast=1.07:brightness=0.02:saturation=1.25",
        "colorbalance=rm=0.05:gm=0.01:bm=-0.05:rh=0.03:bh=-0.03",
        "vibrance=intensity=0.15",
        "unsharp=5:5:%.2f:5:5:0" % sharp,
        "vignette=angle=PI/6",
        # パカーンの瞬間の白フラッシュ
        "drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45:t=fill:enable='between(t,%.2f,%.2f)'"
        % (reveal, reveal + 0.07),
    ]
    if font:
        hook, pop, dish, place = texts
        if hook:
            look.append(_text(tmp, "hook", hook, font, 66, "h*0.12", 0, min(2.8, reveal - 0.6)))
        if pop:
            look.append(_text(tmp, "pop", pop, font, 110, "h*0.40", reveal + 0.05,
                              reveal + 1.6, color="0xFFD23F"))
        if dish:
            look.append(_text(tmp, "dish", dish, font, 56, "h*0.72", max(reveal + 1.7, total - 3.8),
                              total))
        if place:
            look.append(_text(tmp, "place", place, font, 44, "h*0.78", max(reveal + 1.7, total - 3.8),
                              total))
    look.append("format=yuv420p")
    return look


def build_filter(segs, has_audio, reveal, total, texts, tmp, font):
    parts = []
    n = len(segs)
    parts.append("[0:v]split=%d%s" % (n, "".join("[v%d]" % i for i in range(n))))
    if has_audio:
        parts.append("[0:a]asplit=%d%s" % (n, "".join("[a%d]" % i for i in range(n))))
    cat = []
    for i, (s, e, sp) in enumerate(segs):
        v = "[v{i}]trim={s:.3f}:{e:.3f},setpts=(PTS-STARTPTS)/{sp}".format(i=i, s=s, e=e, sp=sp)
        if sp < 1:
            v += ",minterpolate=fps=%d:mi_mode=blend" % FPS
        parts.append(v + ",fps=%d[sv%d]" % (FPS, i))
        if has_audio:
            parts.append("[a{i}]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,atempo={sp}[sa{i}]"
                         .format(i=i, s=s, e=e, sp=sp))
        else:
            parts.append("anullsrc=r=%d:cl=mono,atrim=0:%.3f[sa%d]" % (SR, (e - s) / sp, i))
        cat.append("[sv%d][sa%d]" % (i, i))
    parts.append("%sconcat=n=%d:v=1:a=1[cv][ca]" % ("".join(cat), n))

    look = look_chain(reveal, total, texts, tmp, font)
    parts.append("[cv]" + ",".join(look) + "[outv]")

    # 実音のジュージューを前に出す（高域を持ち上げて圧縮）
    parts.append("[ca]aformat=channel_layouts=mono,highpass=f=90,"
                 "equalizer=f=5500:t=q:w=1.2:g=5,"
                 "acompressor=threshold=-24dB:ratio=3:attack=5:release=150:makeup=3[real]")
    parts.append("[1:a]aformat=channel_layouts=mono[bed]")
    parts.append("[real][bed]amix=inputs=2:weights='1 0.8':normalize=0:duration=first,"
                 "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=%d,"
                 "aformat=channel_layouts=stereo[outa]" % SR)
    return ";".join(parts)


def render(src, out, reveal=None, start=0.0, end=None, hook="Watch it open.",
           pop="PAKAAN!", dish="", price=None, place="JAPAN FOOD HUB · SABURTALO"):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg がありません（Macなら GitHub の inbox/ に置けば Actions が作ります）")
    dur, has_audio = probe(src)
    end = dur if end is None else min(end, dur)
    if reveal is None:
        reveal = start + (end - start) * 0.65
    segs, out_reveal, total = timeline(start, end, reveal)
    if total > 90:
        raise ValueError("完成が %.0f 秒になります。--start / --end で90秒以内に絞ってください" % total)

    dish_line = dish + (" · %s GEL" % price if price else "") if dish else ""
    texts = (hook, pop, dish_line, place)
    font = find_font()
    if not font:
        print("※ 文字用のフォントが見つからないため、文字なしで作ります", file=sys.stderr)

    tmp = tempfile.mkdtemp(prefix="reel_")
    try:
        bed = os.path.join(tmp, "bed.wav")
        write_wav(bed, synth_bed(total + 0.5, out_reveal))
        fc = build_filter(segs, has_audio, out_reveal, total, texts, tmp, font)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-i", bed,
               "-filter_complex", fc, "-map", "[outv]", "-map", "[outa]",
               "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
               "-maxrate", "8M", "-bufsize", "16M", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
               "-movflags", "+faststart", "-t", "%.3f" % total, out]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    size = os.path.getsize(out) / 1e6
    if size >= 100:
        raise RuntimeError("完成ファイルが %.0fMB あります（GitHubは100MB未満）" % size)
    print("できました: %s（%.1f秒・%.1fMB・パカーンは %.1f 秒目）" % (out, total, size, out_reveal))
    return total


def render_montage(segments, out, reveal_index, hook="", pop="", dish="", price=None,
                   place="JAPAN FOOD HUB · SABURTALO"):
    """複数の動画から区間をつなげて1本のリールにする。

    segments: [(元動画のパス, 開始秒, 終了秒, 速度), ...]  速度 2.0 = 2倍速、0.5 = スロー
    reveal_index: この区間の頭で白フラッシュ＋ポン＋キラッ（いちばん美味しそうな瞬間）
    実音（ジュージュー）は強調して残し、合成BGMと効果音を重ねる。
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg がありません")
    srcs = []
    for p, *_ in segments:
        if p not in srcs:
            srcs.append(p)
    audio = {p: probe(p)[1] for p in srcs}
    lens = [(e - s0) / sp for _, s0, e, sp in segments]
    total = sum(lens)
    reveal = sum(lens[:reveal_index])
    if total > 90:
        raise ValueError("完成が %.0f 秒になります（90秒以内に）" % total)

    tmp = tempfile.mkdtemp(prefix="montage_")
    try:
        bed = os.path.join(tmp, "bed.wav")
        write_wav(bed, synth_bed(total + 0.5, reveal))
        cmd = ["ffmpeg", "-y", "-v", "error"]
        for p in srcs:
            cmd += ["-i", p]
        cmd += ["-i", bed]
        parts, cat = [], []
        uses = {p: sum(1 for q, *_ in segments if q == p) for p in srcs}
        vlabels = {p: iter(["v%d_%d" % (srcs.index(p), k) for k in range(uses[p])]) for p in srcs}
        alabels = {p: iter(["a%d_%d" % (srcs.index(p), k) for k in range(uses[p])]) for p in srcs}
        for p in srcs:
            i = srcs.index(p)
            parts.append("[%d:v]split=%d%s" % (i, uses[p], "".join("[v%d_%d]" % (i, k) for k in range(uses[p]))))
            if audio[p]:
                parts.append("[%d:a]asplit=%d%s" % (i, uses[p], "".join("[a%d_%d]" % (i, k) for k in range(uses[p]))))
        for n, (p, s0, e, sp) in enumerate(segments):
            v = ("[{l}]trim={s:.3f}:{e:.3f},setpts=(PTS-STARTPTS)/{sp},"
                 "scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1").format(
                     l=next(vlabels[p]), s=s0, e=e, sp=sp, w=W, h=H)
            if sp < 1:
                v += ",minterpolate=fps=%d:mi_mode=blend" % FPS
            parts.append(v + ",fps=%d[sv%d]" % (FPS, n))
            if audio[p]:
                parts.append("[{l}]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS,atempo={sp},"
                             "aformat=sample_rates={sr}:channel_layouts=mono[sa{n}]".format(
                                 l=next(alabels[p]), s=s0, e=e, sp=sp, sr=SR, n=n))
            else:
                parts.append("anullsrc=r=%d:cl=mono,atrim=0:%.3f[sa%d]" % (SR, lens[n], n))
            cat.append("[sv%d][sa%d]" % (n, n))
        parts.append("%sconcat=n=%d:v=1:a=1[cv][ca]" % ("".join(cat), len(segments)))
        dish_line = dish + (" · %s GEL" % price if price else "") if dish else ""
        look = look_chain(reveal, total, (hook, pop, dish_line, place), tmp, find_font(), crop=False)
        parts.append("[cv]" + ",".join(look) + "[outv]")
        parts.append("[ca]highpass=f=90,equalizer=f=5500:t=q:w=1.2:g=5,"
                     "acompressor=threshold=-24dB:ratio=3:attack=5:release=150:makeup=3[real]")
        parts.append("[%d:a]aformat=channel_layouts=mono[bed]" % len(srcs))
        parts.append("[real][bed]amix=inputs=2:weights='1 0.8':normalize=0:duration=first,"
                     "loudnorm=I=-14:TP=-1.5:LRA=11,volume=2dB,alimiter=limit=0.7:level=false,"
                     "aresample=%d,aformat=channel_layouts=stereo[outa]" % SR)
        cmd += ["-filter_complex", ";".join(parts), "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
                "-maxrate", "8M", "-bufsize", "16M", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
                "-movflags", "+faststart", "-t", "%.3f" % total, out]
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("できました: %s（%.1f秒・%.1fMB・見せ場は %.1f 秒目）" % (out, total, os.path.getsize(out) / 1e6, reveal))
    return total


STEP_SEC, HERO_SEC = 2.0, 5.0


def render_slides(steps, hero, out, hook="", pop="", dish="", price=None,
                  place="JAPAN FOOD HUB · SABURTALO"):
    """写真（動画から切り出した静止画でもよい）からリールを作る。

    steps: 調理の途中の写真（順番どおり）。1枚 2秒、ゆっくりズーム。
    hero : 完成写真。5秒かけて横に流し、入った瞬間にフラッシュ＋ポン＋キラッ。
    音は実音が無いので、ジュージュー・BGM・効果音をすべて合成する。
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg がありません")
    reveal = STEP_SEC * len(steps)
    total = reveal + HERO_SEC
    frames = int(STEP_SEC * FPS)
    tmp = tempfile.mkdtemp(prefix="slides_")
    try:
        bed = os.path.join(tmp, "bed.wav")
        write_wav(bed, synth_bed(total + 0.5, reveal, sizzle_until=reveal))
        cmd = ["ffmpeg", "-y", "-v", "error"]
        parts = []
        for i, img in enumerate(steps):
            cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "%.2f" % STEP_SEC, "-i", img]
            parts.append(
                "[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
                "crop={w}:{h},setsar=1,zoompan=z='1+0.07*on/{f}':x='iw/2-(iw/zoom/2)'"
                ":y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}[p{i}]".format(
                    i=i, w=W, h=H, f=frames, fps=FPS))
        k = len(steps)
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "%.2f" % HERO_SEC, "-i", hero]
        # 完成写真は高さを合わせ、横長なら左→右へゆっくり流す
        parts.append(
            "[{k}:v]scale=-2:{h}:flags=lanczos,scale='max(iw,{w})':-2,crop={w}:{h}:"
            "x='(iw-{w})*t/{d}':y='(ih-{h})/2',setsar=1,fps={fps}[p{k}]".format(
                k=k, w=W, h=H, d=HERO_SEC, fps=FPS))
        cmd += ["-i", bed]
        parts.append("%sconcat=n=%d:v=1:a=0[cv]" % ("".join("[p%d]" % i for i in range(k + 1)), k + 1))
        dish_line = dish + (" · %s GEL" % price if price else "") if dish else ""
        font = find_font()
        look = look_chain(reveal, total, (hook, pop, dish_line, place), tmp, font,
                          crop=False, sharp=0.4)
        parts.append("[cv]" + ",".join(look) + "[outv]")
        parts.append("[%d:a]loudnorm=I=-14:TP=-1.5:LRA=11,volume=3dB,alimiter=limit=0.7:level=false,aresample=%d,"
                     "aformat=channel_layouts=stereo[outa]" % (k + 1, SR))
        cmd += ["-filter_complex", ";".join(parts), "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
                "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", str(SR),
                "-movflags", "+faststart", "-t", "%.3f" % total, out]
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("できました: %s（%.1f秒・%.1fMB）" % (out, total, os.path.getsize(out) / 1e6))
    return total


# ---------------------------------------------------------------- reels.json 登録

def caption_for(dish, price):
    if dish:
        head = "Watch it open. %s%s.\n\n" % (dish, " — ₾%s" % price if price else "")
        ka = "უყურე როგორ იხსნება. %s%s.\n\n" % (dish, " — ₾%s" % price if price else "")
    else:
        head = "Watch it open. Every omurice is cooked to order.\n\n"
        ka = "უყურე როგორ იხსნება. ყოველი ომურაისი — შეკვეთისთანავე.\n\n"
    jp = "パカーン。一皿ずつ、注文が入ってから焼いています。\n\n"
    return head + ka + jp + ADDRESS + "\n\n" + TAGS


def next_id(reels):
    nums = [int(m.group(1)) for k in reels["posts"] for m in [re.match(r"R(\d+)$", k)] if m]
    return "R%d" % (max(nums or [0]) + 1)


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:30] or "omurice"


def register(reels, video_rel, dish, price, title=None):
    rid = next_id(reels)
    reels["posts"][rid] = {
        "id": rid,
        "title": title or ("Pakaan! — %s" % (dish or "omurice")),
        "video": video_rel,
        "caption": caption_for(dish, price),
    }
    reels["order"].append(rid)
    return rid


def load_reels():
    with open(os.path.join(ROOT, "reels.json"), encoding="utf-8") as f:
        return json.load(f)


def save_reels(reels):
    with open(os.path.join(ROOT, "reels.json"), "w", encoding="utf-8") as f:
        json.dump(reels, f, ensure_ascii=False, indent=2)
        f.write("\n")


def make_and_register(src, opts, keep_source=True):
    reels = load_reels()
    rid = next_id(reels)
    rel = "reels/%s_%s.mp4" % (rid, slug(opts.get("dish") or "pakaan"))
    render(src, os.path.join(ROOT, rel), reveal=opts.get("reveal"), start=opts.get("start", 0.0),
           end=opts.get("end"), hook=opts.get("hook", "Watch it open."),
           pop=opts.get("pop", "PAKAAN!"), dish=opts.get("dish", ""), price=opts.get("price"),
           place=opts.get("place", "JAPAN FOOD HUB · SABURTALO"))
    register(reels, rel, opts.get("dish", ""), opts.get("price"), opts.get("title"))
    save_reels(reels)
    print("reels.json に %s として登録しました（次の月・水・金に投稿されます）" % rid)
    if not keep_source:
        os.remove(src)
    return rid


def inbox_opts(path):
    """inbox の動画ごとの設定。ファイル名の _t14.5 と、同名 .json を読む。"""
    stem = os.path.splitext(path)[0]
    opts = {}
    m = re.search(r"_t(\d+(?:\.\d+)?)", os.path.basename(stem))
    if m:
        opts["reveal"] = float(m.group(1))
    side = stem + ".json"
    if os.path.exists(side):
        with open(side, encoding="utf-8") as f:
            opts.update(json.load(f))
    return opts, (side if os.path.exists(side) else None)


def run_inbox():
    if not os.path.isdir(INBOX):
        print("inbox/ がありません")
        return 0
    files = sorted(f for f in os.listdir(INBOX) if f.lower().endswith(VIDEO_EXT))
    if not files:
        print("inbox/ に新しい動画はありません")
        return 0
    for name in files:
        path = os.path.join(INBOX, name)
        opts, side = inbox_opts(path)
        print("\n== %s %s" % (name, json.dumps(opts, ensure_ascii=False)))
        make_and_register(path, opts, keep_source=False)
        if side:
            os.remove(side)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="オムライス動画を投稿用リールに自動編集する")
    ap.add_argument("src", nargs="?", help="元動画（.mov / .mp4）")
    ap.add_argument("--inbox", action="store_true", help="inbox/ の動画をまとめて処理")
    ap.add_argument("--reveal", type=float, help="パカーンの瞬間（元動画の秒）")
    ap.add_argument("--start", type=float, default=0.0, help="使い始める秒")
    ap.add_argument("--end", type=float, help="使い終わる秒")
    ap.add_argument("--dish", default="", help='料理名（例 "No.01 Classic Omurice"）')
    ap.add_argument("--price", help="価格（ラリ）")
    ap.add_argument("--hook", default="Watch it open.", help="冒頭の一言")
    ap.add_argument("--pop", default="PAKAAN!", help="パカーンの瞬間の文字")
    ap.add_argument("--place", default="JAPAN FOOD HUB · SABURTALO", help="最後の店名（空で消す）")
    ap.add_argument("--no-text", action="store_true", help="冒頭と最後の文字を入れない（文字入りの素材用）")
    ap.add_argument("--out", help="出力先だけ指定して reels.json には登録しない（試し用）")
    a = ap.parse_args(argv)

    if a.no_text:
        a.hook = a.place = ""
    if a.inbox:
        return run_inbox()
    if not a.src:
        ap.error("元動画を指定するか --inbox を付けてください")
    opts = {k: v for k, v in vars(a).items() if v not in (None, "") and k not in ("src", "inbox", "out", "no_text")}
    opts.setdefault("hook", a.hook)
    opts.setdefault("place", a.place)
    if a.out:
        render(a.src, a.out, reveal=a.reveal, start=a.start, end=a.end, hook=a.hook, pop=a.pop,
               dish=a.dish, price=a.price, place=a.place)
        return 0
    make_and_register(a.src, opts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
