#!/usr/bin/env python3
"""ジョージア風のかっこいいBGMを自前で合成する（著作権の心配なし・標準ライブラリのみ）。

  georgian_bed(秒数, 見せ場の秒, seed) -> float 配列（モノラル・-1〜1）

- 6/8 拍子（ジョージアの踊りの曲に多いリズム）、Aドリアン
- パンドゥリ（3弦のはじく楽器）… Karplus-Strong でかき鳴らす
- ドリ（太鼓）… 低い「ドン」と皮をはたく「タッ」
- ドローン（持続音）… ジョージアの多声合唱のような A と E の低音
- サラムリ（笛）… 見せ場のあとに短いフレーズ
見せ場の直前は一瞬ブレイクし、見せ場で全員が入る。
"""
import array
import math
import random

SR = 48000
EIGHTH = 0.2            # 8分音符 = 0.2秒（付点4分 = 100 BPM）
BAR = 6 * EIGHTH        # 6/8 の1小節

# Am – G – Am – F – Am – G – Em – Am（ジョージア民謡っぽい短調の進行）
PROG = [(57, [57, 64, 69]), (55, [55, 62, 67]), (57, [57, 64, 69]), (53, [53, 60, 65]),
        (57, [57, 64, 69]), (55, [55, 62, 67]), (52, [52, 59, 64]), (57, [57, 64, 69])]
# サラムリのフレーズ（A ドリアン: A B C D E F# G）
MELODY = [(81, 1), (79, 1), (78, 1), (76, 3), (74, 1), (76, 1), (78, 1), (76, 3),
          (81, 1), (83, 1), (81, 1), (79, 1), (78, 1), (76, 1), (74, 2), (76, 4)]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


class Buf:
    def __init__(self, sec):
        self.n = int(sec * SR)
        self.a = array.array("f", bytes(4 * self.n))

    def add(self, t0, samples, gain=1.0):
        i0 = int(t0 * SR)
        a, n = self.a, self.n
        for k, v in enumerate(samples):
            i = i0 + k
            if i >= n:
                break
            if i >= 0:
                a[i] += v * gain


def pluck(freq, dur, rnd, bright=0.5):
    """Karplus-Strong（弦をはじいた音）。"""
    p = max(2, int(SR / freq))
    ring = [rnd.uniform(-1, 1) for _ in range(p)]
    for _ in range(2):   # 最初のノイズを丸めて、耳に痛い「カチッ」を減らす
        ring = [0.5 * (ring[i] + ring[i - 1]) for i in range(p)]
    out = []
    n = int(dur * SR)
    decay = 0.996
    idx = 0
    prev = 0.0
    for k in range(n):
        v = ring[idx]
        nxt = ring[(idx + 1) % p]
        new = decay * (bright * v + (1 - bright) * 0.5 * (v + nxt))
        ring[idx] = new
        idx = (idx + 1) % p
        out.append(v)
        prev = v
    # 立ち上がりのクリック防止＋終わりのフェード
    fade = min(n, int(0.03 * SR))
    for k in range(fade):
        out[n - 1 - k] *= k / fade
    return out


def doli_low(rnd):
    n = int(0.35 * SR)
    out = []
    ph = 0.0
    for k in range(n):
        t = k / SR
        f = 55 + 70 * math.exp(-t * 30)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 9))
    return out


def doli_slap(rnd):
    n = int(0.09 * SR)
    out, lp = [], 0.0
    for k in range(n):
        t = k / SR
        w = rnd.uniform(-1, 1)
        lp += 0.35 * (w - lp)
        out.append((w - lp) * math.exp(-t * 45) + 0.4 * math.sin(2 * math.pi * 330 * t) * math.exp(-t * 60))
    return out


def drone(freqs, dur):
    n = int(dur * SR)
    out = []
    for k in range(n):
        t = k / SR
        v = 0.0
        for j, f in enumerate(freqs):
            v += math.sin(2 * math.pi * f * t) + 0.35 * math.sin(2 * math.pi * 2 * f * t + j)
        env = min(1.0, t / 0.8) * min(1.0, (dur - t) / 0.8)
        out.append(v * env / len(freqs))
    return out


def flute(freq, dur, rnd):
    n = int(dur * SR)
    out, lp = [], 0.0
    for k in range(n):
        t = k / SR
        vib = 1 + 0.006 * math.sin(2 * math.pi * 5.5 * t) * min(1, t / 0.15)
        w = rnd.uniform(-1, 1)
        lp += 0.05 * (w - lp)
        env = min(1.0, t / 0.04) * min(1.0, (dur - t) / 0.06)
        out.append(env * (math.sin(2 * math.pi * freq * vib * t) + 0.15 * math.sin(4 * math.pi * freq * t) + 0.25 * lp))
    return out


def georgian_bed(total, reveal=None, seed=7):
    rnd = random.Random(seed)
    b = Buf(total)
    reveal = reveal if reveal is not None else total * 0.6
    low, slap = doli_low(rnd), doli_slap(rnd)

    # ドローン（全体に薄く）
    b.add(0, drone([hz(45), hz(52)], total), 0.10)

    t, k = 0.0, 0
    while t < total:
        root, chord = PROG[k % len(PROG)]
        building = t < 2 * BAR               # 最初の2小節はパンドゥリだけ
        in_break = reveal - 0.6 <= t < reveal
        # パンドゥリのかき鳴らし（6/8: ↓ . ↑ ↓ ↑ ↓）
        for step, (on, gain) in enumerate([(1, 1.0), (0, 0), (1, 0.55), (1, 0.85), (1, 0.5), (1, 0.7)]):
            ts = t + step * EIGHTH
            if not on or ts >= total or (reveal - 0.6 <= ts < reveal):
                continue
            for j, m in enumerate(chord):
                b.add(ts + j * 0.012, pluck(hz(m + 12), 0.45, rnd, 0.35), 0.13 * gain)
        # ベース（1拍目と4拍目）
        for step in (0, 3):
            ts = t + step * EIGHTH
            if ts < total and not in_break:
                b.add(ts, pluck(hz(root - 12), 0.6, rnd, 0.3), 0.30)
        # ドリ（ドン . タッ ドン タッ .）
        if not building:
            for step, kind in [(0, "L"), (2, "S"), (3, "L"), (4, "S"), (5, "s")]:
                ts = t + step * EIGHTH
                if ts >= total or (reveal - 0.6 <= ts < reveal):
                    continue
                if kind == "L":
                    b.add(ts, low, 0.55)
                else:
                    b.add(ts, slap, 0.28 if kind == "S" else 0.14)
        t += BAR
        k += 1

    # 見せ場のあとにサラムリ（笛）のフレーズ
    ts = reveal + 0.1
    for m, beats in MELODY:
        d = beats * EIGHTH
        if ts + d > total - 0.3:
            break
        b.add(ts, flute(hz(m), d * 0.95, rnd), 0.10)
        ts += d

    # 見せ場で「ジャン！」（全音域のかき鳴らし）
    for j, m in enumerate([45, 52, 57, 64, 69, 76]):
        b.add(reveal + j * 0.01, pluck(hz(m), 1.4, rnd, 0.6), 0.16)

    a = b.a
    peak = max(1e-9, max(abs(v) for v in a))
    g = 0.9 / peak
    fi, fo = int(0.3 * SR), int(1.5 * SR)
    for i in range(b.n):
        a[i] *= g
    for i in range(min(fi, b.n)):
        a[i] *= i / fi
    for i in range(min(fo, b.n)):
        a[b.n - 1 - i] *= i / fo
    return a


if __name__ == "__main__":
    import sys
    import make_reel as M
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    M.write_wav(sys.argv[2] if len(sys.argv) > 2 else "georgian.wav", georgian_bed(sec, sec * 0.5))
