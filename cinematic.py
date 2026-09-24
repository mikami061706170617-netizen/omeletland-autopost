#!/usr/bin/env python3
"""料理ドラマ風のシネマティックBGMを自前で合成する（オリジナル曲・標準ライブラリのみ）。

  grand_bed(秒数, 見せ場の秒, seed) -> float 配列（モノラル・-1〜1）

構成（D マイナー、120 BPM）
  1. イントロ   … 低いピアノのオクターブ＋弦のうねり
  2. ビルド     … 16分音符で刻む弦（スタッカート）＋低弦の8分＋ティンパニ。見せ場に向けて強くなる
  3. ため       … 見せ場の直前 0.7 秒はほぼ無音にして、上昇音（ライザー）だけ
  4. 見せ場     … オーケストラヒット（ティンパニ＋金管＋シンバル）
  5. 余韻       … ゆったりした和音の上に、ピアノの旋律（オリジナル）。最後は D メジャーで明るく終わる
仕上げに簡単なリバーブ（Schroeder）をかける。
"""
import array
import math
import random

SR = 48000
BPM = 120.0
BEAT = 60.0 / BPM          # 0.5 秒
SIX = BEAT / 4             # 16分音符 0.125 秒

# Dm – B♭ – F – C（i–VI–III–VII）
PROG = [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]]
BASS = [38, 34, 41, 36]
# 見せ場のあとのピアノの旋律（オリジナル、D マイナー → 最後は D メジャー）
MELODY = [(74, 1.5), (76, 0.5), (77, 1.0), (76, 1.0), (74, 1.5), (72, 0.5), (69, 2.0),
          (70, 1.0), (72, 1.0), (74, 1.0), (77, 1.0), (76, 1.5), (74, 0.5), (73, 1.0), (74, 3.0)]


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


def _saw_ens(freq, dur, att, rel, cutoff):
    """デチューンした3本のノコギリ波（弦・金管の素）＋1極ローパス。"""
    n = int(dur * SR)
    out = []
    ph = [0.0, 0.33, 0.66]
    det = [1.0, 1.004, 0.996]
    lp = 0.0
    a = 2 * math.pi * cutoff / SR
    alpha = a / (a + 1)
    for k in range(n):
        v = 0.0
        for j in range(3):
            ph[j] += freq * det[j] / SR
            ph[j] -= int(ph[j])
            v += 2 * ph[j] - 1
        lp += alpha * (v / 3 - lp)
        t = k / SR
        env = min(1.0, t / att) * min(1.0, max(0.0, (dur - t) / rel))
        out.append(lp * env)
    return out


def string_stab(freq):
    return _saw_ens(freq, SIX * 0.9, 0.006, 0.05, 2600)


def string_pad(freq, dur, cutoff=1800):
    return _saw_ens(freq, dur, min(0.6, dur / 3), min(0.8, dur / 3), cutoff)


def brass(freq, dur):
    return _saw_ens(freq, dur, 0.04, 0.5, 1400)


def piano(freq, dur):
    n = int(dur * SR)
    out = []
    parts = [(1, 1.0, 3.0), (2, 0.45, 4.5), (3, 0.25, 6.0), (4, 0.12, 8.0), (5, 0.06, 10.0)]
    for k in range(n):
        t = k / SR
        v = 0.0
        for h, g, d in parts:
            v += g * math.sin(2 * math.pi * freq * h * 1.0006 ** h * t) * math.exp(-t * d * 0.6)
        out.append(v * min(1.0, t / 0.003) * min(1.0, (dur - t) / 0.05))
    return out


def timpani(freq=46.0):
    n = int(1.1 * SR)
    out, ph = [], 0.0
    rnd = random.Random(3)
    for k in range(n):
        t = k / SR
        f = freq * (1 + 0.5 * math.exp(-t * 25))
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 3.2) + 0.25 * rnd.uniform(-1, 1) * math.exp(-t * 40))
    return out


def cymbal():
    rnd = random.Random(5)
    n = int(2.5 * SR)
    out, prev = [], 0.0
    for k in range(n):
        t = k / SR
        w = rnd.uniform(-1, 1)
        hp, prev = w - prev, w
        out.append(hp * math.exp(-t * 1.6) * min(1.0, t / 0.002))
    return out


def riser(dur):
    rnd = random.Random(9)
    n = int(dur * SR)
    out, lp = [], 0.0
    for k in range(n):
        x = k / n
        a = 2 * math.pi * (300 + 7000 * x * x) / SR
        lp += a / (a + 1) * (rnd.uniform(-1, 1) - lp)
        out.append(lp * x ** 2)
    return out


def reverb(a, mix=0.22):
    """Schroeder リバーブ（コム4本＋オールパス2本）。"""
    n = len(a)
    wet = array.array("f", bytes(4 * n))
    for d, g in ((1557, 0.80), (1617, 0.79), (1491, 0.78), (1422, 0.77)):
        d = int(d * SR / 44100)
        buf = array.array("f", bytes(4 * n))
        for i in range(n):
            y = a[i] + (g * buf[i - d] if i >= d else 0.0)
            buf[i] = y
            wet[i] += y * 0.25
    for d, g in ((225, 0.7), (556, 0.7)):
        d = int(d * SR / 44100)
        x = array.array("f", wet)
        for i in range(n):
            xd = x[i - d] if i >= d else 0.0
            yd = wet[i - d] if i >= d else 0.0
            wet[i] = -g * x[i] + xd + g * yd
    for i in range(n):
        a[i] = a[i] * (1 - mix) + wet[i] * mix
    return a


def grand_bed(total, reveal=None, seed=11):
    reveal = reveal if reveal is not None else total * 0.6
    b = Buf(total)
    bar = 4 * BEAT
    brk = 0.7                                  # ため（ほぼ無音）

    # 1. イントロ: 低いピアノ＋弦のうねり
    b.add(0, piano(hz(38), 3.0), 0.35)
    b.add(0, piano(hz(50), 3.0), 0.25)

    # 2. ビルド（見せ場の直前まで）
    t, k = 0.0, 0
    build_end = max(0.0, reveal - brk)
    while t < build_end:
        chord, bass = PROG[k % 4], BASS[k % 4]
        prog = min(1.0, (t + bar) / max(bar, build_end))       # 0→1 でだんだん強く
        # 弦の刻み（16分）: 和音の音を上下に
        pattern = [chord[0], chord[1], chord[2], chord[1]] * 4
        for s, m in enumerate(pattern):
            ts = t + s * SIX
            if ts >= build_end:
                break
            acc = 1.0 if s % 4 == 0 else 0.6
            b.add(ts, string_stab(hz(m + 12)), (0.16 + 0.14 * prog) * acc)
        # 低弦の8分
        for s in range(8):
            ts = t + s * BEAT / 2
            if ts < build_end:
                b.add(ts, string_stab(hz(bass)), 0.20 + 0.10 * prog)
        # 弦のパッド（厚み）
        b.add(t, string_pad(hz(chord[0]), min(bar, build_end - t + 0.2)), 0.10 + 0.08 * prog)
        # ティンパニ（1拍目と3拍目、後半は毎拍）
        for s in range(4):
            if s in (0, 2) or prog > 0.6:
                ts = t + s * BEAT
                if ts < build_end:
                    b.add(ts, timpani(46 if s % 2 == 0 else 55), 0.12 + 0.12 * prog)
        t += bar
        k += 1

    # 3. ため: 上昇音だけ
    if reveal - brk > 0:
        b.add(reveal - brk, riser(brk), 0.25)

    # 4. 見せ場: オーケストラヒット
    for m in (38, 50, 57, 62, 65):
        b.add(reveal, brass(hz(m), 1.6), 0.16)
    b.add(reveal, timpani(46), 0.45)
    b.add(reveal, cymbal(), 0.18)
    b.add(reveal, piano(hz(38), 2.5), 0.4)

    # 5. 余韻: ゆったりした和音＋ピアノの旋律
    t, k = reveal + 0.5, 0
    while t < total:
        chord, bass = PROG[k % 4], BASS[k % 4]
        dur = min(bar, total - t)
        b.add(t, string_pad(hz(chord[0] + 12), dur + 0.3, 2200), 0.14)
        b.add(t, string_pad(hz(chord[2]), dur + 0.3, 2200), 0.11)
        b.add(t, string_pad(hz(bass), dur + 0.3, 900), 0.12)
        # 刻みは小さく残す（前に進む感じ）
        for s in range(8):
            ts = t + s * BEAT / 2
            if ts < total:
                b.add(ts, string_stab(hz(chord[s % 3] + 12)), 0.08)
        t += bar
        k += 1
    ts = reveal + 0.6
    for m, beats in MELODY:
        d = beats * BEAT
        if ts + d > total - 0.2:
            break
        b.add(ts, piano(hz(m), d + 0.4), 0.34)
        ts += d
    # 最後は D メジャーで明るく
    if total - reveal > 3:
        end = total - 2.2
        for m in (50, 54, 57, 62, 66):
            b.add(end, piano(hz(m), 2.2), 0.12)

    a = reverb(b.a)
    peak = max(1e-9, max(abs(v) for v in a))
    g = 0.9 / peak
    fi, fo = int(0.2 * SR), int(1.2 * SR)
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
    sec = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    rv = float(sys.argv[3]) if len(sys.argv) > 3 else sec * 0.55
    M.write_wav(sys.argv[2] if len(sys.argv) > 2 else "grand.wav", grand_bed(sec, rv))
