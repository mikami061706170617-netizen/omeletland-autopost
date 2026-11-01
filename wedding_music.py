#!/usr/bin/env python3
"""結婚式リール用のBGMを自前で合成する（著作権の心配なし・標準ライブラリのみ）。

  wedding_bed(秒数, 見せ場の秒, seed) -> float 配列（モノラル・-1〜1）
    … 教会・ガーデン挙式っぽいピアノと弦。和音の流れはパッヘルベルのカノン（1680年頃・パブリックドメイン）、
      D メジャー 80 BPM。見せ場でベルがキラッと鳴り、そのあとカノンの上の旋律。
  indian_bed(秒数, 見せ場の秒, seed) -> float 配列
    … インドの結婚式っぽい曲（オリジナル）。タンプーラ（持続音）＋ドール（両面太鼓）＋シタール風のはじく音
      ＋シェーナイ風の笛（インドの結婚式の定番の管楽器）。D の Yaman 風（D E F# G# A B C#）、104 BPM。
      見せ場の直前で一瞬ブレイク、見せ場でドールの連打から全員が入る。
"""
import math
import random

import cinematic as C
import music as G

SR = C.SR
Buf = C.Buf
hz = C.hz


# ---------------------------------------------------------------- ウェディング（カノン）
W_BEAT = 0.75
# D – A – Bm – F#m – G – D – G – A（各2拍）
CANON = [(38, [62, 66, 69]), (45, [61, 64, 69]), (47, [62, 66, 71]), (42, [61, 66, 69]),
         (43, [62, 67, 71]), (38, [62, 66, 69]), (43, [62, 67, 71]), (45, [61, 64, 69])]
# カノンの上の旋律（2分音符の下降線）
CANON_TOP = [78, 76, 74, 73, 71, 69, 71, 73]


def bell(freq, dur=2.2):
    n = int(dur * SR)
    out = []
    for k in range(n):
        t = k / SR
        v = (math.sin(2 * math.pi * freq * t) * math.exp(-t * 2.2)
             + 0.5 * math.sin(2 * math.pi * freq * 2.76 * t) * math.exp(-t * 4.0)
             + 0.25 * math.sin(2 * math.pi * freq * 5.4 * t) * math.exp(-t * 7.0))
        out.append(v * min(1.0, t / 0.002))
    return out


def _finish(b, mix=0.25, fade_in=0.3):
    a = C.reverb(b.a, mix) if mix else b.a
    peak = max(1e-9, max(abs(v) for v in a))
    g = 0.9 / peak
    fi, fo = int(fade_in * SR), int(1.8 * SR)
    n = len(a)
    for i in range(n):
        a[i] *= g
    for i in range(min(fi, n)):
        a[i] *= i / fi
    for i in range(min(fo, n)):
        a[n - 1 - i] *= i / fo
    return a


def wedding_bed(total, reveal=None, seed=21):
    reveal = reveal if reveal is not None else total * 0.5
    b = Buf(total)
    step = 2 * W_BEAT
    t, k = 0.0, 0
    while t < total:
        root, chord = CANON[k % len(CANON)]
        intro = t < 2 * step * 2           # 最初の4和音はピアノだけ
        # ピアノの分散和音（8分音符で 根音→3度→5度→オクターブ）
        arp = [root + 12, chord[0], chord[1], chord[2]]
        for j in range(4):
            ts = t + j * W_BEAT / 2
            if ts < total:
                b.add(ts, C.piano(hz(arp[j]), 1.2), 0.20 if j else 0.26)
        # 弦の和音（イントロのあと）
        if not intro:
            for m in chord:
                b.add(t, C.string_pad(hz(m), step + 0.3, 1500), 0.07)
            b.add(t, C.string_pad(hz(root), step + 0.3, 900), 0.10)
        # 見せ場のあとはカノンの上の旋律
        if t >= reveal:
            b.add(t, C.string_pad(hz(CANON_TOP[k % 8]), step * 0.98, 2600), 0.13)
            b.add(t, C.piano(hz(CANON_TOP[k % 8] + 12), 1.4), 0.12)
        t += step
        k += 1
    # 見せ場でベル（D メジャーの和音を上から）
    for j, m in enumerate([86, 81, 78, 74]):
        b.add(reveal + j * 0.09, bell(hz(m)), 0.10)
    return _finish(b, 0.28)


# ---------------------------------------------------------------- インド（Yaman 風）
I_BEAT = 60.0 / 104
I_EIGHTH = I_BEAT / 2
I_BAR = 4 * I_BEAT
SA = 50                     # D3
# シェーナイの旋律（オリジナル。Sa=D、Yaman 風に G# を使う）: (MIDI, 8分音符いくつ)
SHEHNAI = [(74, 2), (76, 1), (78, 1), (80, 2), (81, 4), (80, 1), (78, 1), (76, 2), (78, 2), (74, 4),
           (81, 2), (83, 1), (85, 1), (86, 4), (85, 1), (83, 1), (81, 2), (80, 2), (78, 1), (76, 1), (74, 6)]
# 見せ場まで流すシタールの短いフレーズ（1小節 = 8つの8分音符）
SITAR = [[62, None, 66, 68, 69, None, 68, 66], [64, None, 66, 64, 62, None, 61, 62],
         [69, None, 71, 69, 68, 66, 68, None], [66, 64, 62, None, 64, None, 62, None]]


def tanpura(dur, rnd):
    """Pa–Sa–Sa–Sa(低) をゆっくりはじき続ける。ジャワリ（うなり）は高い倍音のゆらぎで出す。"""
    b = Buf(dur)
    seq = [SA - 5, SA, SA, SA - 12]
    t, j = 0.0, 0
    while t < dur:
        f = hz(seq[j % 4])
        n = int(min(2.4, dur - t) * SR)
        out = []
        for k in range(n):
            s = k / SR
            env = math.exp(-s * 0.9) * min(1.0, s / 0.01)
            buzz = 1 + 0.3 * math.sin(2 * math.pi * 0.7 * s + j)
            v = 0.0
            for h in range(1, 9):
                v += math.sin(2 * math.pi * f * h * s) * (1.0 / h) * (buzz if h > 3 else 1.0)
            out.append(v * env)
        b.add(t, out, 1.0)
        t += 0.6
        j += 1
    return b.a


def dhol_bass(rnd):
    n = int(0.45 * SR)
    out, ph = [], 0.0
    for k in range(n):
        t = k / SR
        f = 62 + 90 * math.exp(-t * 22)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 6.5) + 0.15 * rnd.uniform(-1, 1) * math.exp(-t * 80))
    return out


def dhol_tilli(rnd):
    """細い棒で高い面を打つ「チッ」。"""
    n = int(0.12 * SR)
    out, lp = [], 0.0
    for k in range(n):
        t = k / SR
        w = rnd.uniform(-1, 1)
        lp += 0.5 * (w - lp)
        out.append((w - lp) * math.exp(-t * 38) + 0.5 * math.sin(2 * math.pi * 520 * t) * math.exp(-t * 30))
    return out


def sitar(freq, dur, rnd):
    """Karplus-Strong を明るめに＋最初に少し下からすくい上げる（ミーンド）。"""
    base = G.pluck(freq, dur, rnd, 0.62)
    # 共鳴弦の「シャーン」
    sym = G.pluck(freq * 2, dur, rnd, 0.7)
    return [0.8 * a + 0.25 * s for a, s in zip(base, sym)]


def shehnai(freq, dur):
    """リードの管楽器（シェーナイ風）：倍音の多い波＋ビブラート＋息。"""
    n = int(dur * SR)
    out, ph = [], 0.0
    rnd = random.Random(int(freq))
    lp = 0.0
    for k in range(n):
        t = k / SR
        vib = 1 + 0.012 * math.sin(2 * math.pi * 6.0 * t) * min(1.0, t / 0.2)
        glide = 1 - 0.03 * math.exp(-t * 25)       # 音の頭で少し下からすくう
        ph += 2 * math.pi * freq * vib * glide / SR
        v = (math.sin(ph) + 0.6 * math.sin(2 * ph) + 0.45 * math.sin(3 * ph)
             + 0.3 * math.sin(4 * ph) + 0.2 * math.sin(5 * ph))
        lp += 0.2 * (rnd.uniform(-1, 1) - lp)
        env = min(1.0, t / 0.04) * min(1.0, (dur - t) / 0.05)
        out.append((v * 0.5 + 0.06 * lp) * env)
    return out


def indian_bed(total, reveal=None, seed=31):
    rnd = random.Random(seed)
    reveal = reveal if reveal is not None else total * 0.5
    b = Buf(total)
    br0, br1 = reveal - 0.55, reveal
    b.add(0, tanpura(total, rnd), 0.06)
    bass, tilli = dhol_bass(rnd), dhol_tilli(rnd)
    # ドールのチャール（バングラのはずむリズム）: 8分音符 8つ
    CHAAL = [("B", 1.0), ("T", 0.5), (None, 0), ("T", 0.7), ("B", 0.8), ("T", 0.5), ("B", 0.6), ("T", 0.6)]
    t, k = 0.0, 0
    while t < total:
        build = t < I_BAR
        for j, (kind, g) in enumerate(CHAAL):
            ts = t + j * I_EIGHTH
            if kind is None or ts >= total or br0 <= ts < br1:
                continue
            if build and kind == "B" and j:
                continue
            b.add(ts, bass if kind == "B" else tilli, (0.5 if kind == "B" else 0.15) * g)
        # シタールのフレーズ（見せ場まで）
        if t < reveal:
            for j, m in enumerate(SITAR[k % 4]):
                ts = t + j * I_EIGHTH
                if m is None or ts >= total or br0 <= ts < br1:
                    continue
                b.add(ts, sitar(hz(m), 0.7, rnd), 0.12)
        # ベース（Sa と Pa）
        for j, m in ((0, SA - 12), (4, SA - 5 - 12)):
            ts = t + j * I_EIGHTH
            if ts < total and not (br0 <= ts < br1) and not build:
                b.add(ts, G.pluck(hz(m), 0.5, rnd, 0.3), 0.22)
        t += I_BAR
        k += 1
    # 見せ場：ドールの連打（ブレイクの中）→ 全員
    ts = br0
    while ts < br1:
        b.add(ts, tilli, 0.18)
        ts += I_EIGHTH / 2
    b.add(reveal, bass, 0.75)
    for j, m in enumerate([SA - 12, SA, SA + 7, SA + 12, SA + 16, SA + 19]):
        b.add(reveal + j * 0.012, sitar(hz(m), 1.6, rnd), 0.12)
    # 見せ場のあとシェーナイ
    ts = reveal + I_EIGHTH
    for m, n8 in SHEHNAI:
        d = n8 * I_EIGHTH
        if ts + d > total - 0.4:
            break
        b.add(ts, shehnai(hz(m), d * 0.96), 0.11)
        ts += d
    return _finish(b, 0.12, 0.2)


if __name__ == "__main__":
    import sys
    import make_reel as M
    kind = sys.argv[1] if len(sys.argv) > 1 else "wedding"
    sec = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    fn = indian_bed if kind == "indian" else wedding_bed
    M.write_wav(sys.argv[3] if len(sys.argv) > 3 else kind + ".wav", fn(sec, sec * 0.45))
