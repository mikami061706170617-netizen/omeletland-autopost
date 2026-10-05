#!/usr/bin/env python3
"""できあがった動画（本人が作ったもの・編集済みのもの）を、そのままリールの順番に入れる。

  python3 add_reel.py 動画.mov --title "寿司はじめました" --caption キャプション.txt
  python3 add_reel.py 動画.mov --dish "Salmon Nigiri" --price 18      （キャプションを自動で作る）

- 1080×1920（縦）でなければ中央を切り抜いて合わせる（ぼかし帯は入れない）
- 色の印は必ず SDR（bt709）にする（HDR の印が残るとインスタで真っ暗になる）
- 100MB 未満に収める
- reels/R<次の番号>_<名前>.mp4 に置いて reels.json の最後に足す（次の空いた日の 20:00 に出る）
標準ライブラリ＋ffmpeg のみ。終わったら python3 test_logic.py を通してから push する。
"""
import argparse
import json
import os
import subprocess
import sys

import make_reel as M

ROOT = os.path.dirname(os.path.abspath(__file__))
LIMIT = 95e6


def info(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,color_transfer:format=duration",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in d["streams"])
    return v["width"], v["height"], v.get("color_transfer", ""), float(d["format"]["duration"]), has_audio


def normalize(src, out):
    """1080×1920・SDR・AAC・100MB 未満の mp4 にする。"""
    w, h, trc, dur, has_audio = info(src)
    rate = min(8.0, LIMIT * 8 / 1e6 / max(dur, 1) * 0.9)          # Mbps
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1"
          % (M.W, M.H, M.W, M.H))
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=%d:cl=stereo" % M.SR, "-shortest"]
    cmd += ["-vf", vf, "-r", str(M.FPS), "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20", *M.SDR,
            "-maxrate", "%.1fM" % rate, "-bufsize", "16M",
            "-c:a", "aac", "-b:a", "160k", "-ar", str(M.SR), "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    if os.path.getsize(out) >= 100e6:
        raise RuntimeError("100MB を超えました。動画を短くしてください: %s" % out)
    return dur


def main(argv=None):
    ap = argparse.ArgumentParser(description="できあがった動画をリールの順番に入れる")
    ap.add_argument("src", help="動画ファイル（.mov / .mp4）")
    ap.add_argument("--title", help="管理用の題（例: Sushi — salmon nigiri）")
    ap.add_argument("--caption", help="キャプションを書いたテキストファイル（2200字・タグ30個まで）")
    ap.add_argument("--dish", default="", help="料理名（--caption が無いときの自動キャプション用）")
    ap.add_argument("--price", help="価格（ラリ）")
    ap.add_argument("--slug", help="ファイル名に使う英字（省略時は料理名から）")
    ap.add_argument("--dry-run", action="store_true", help="書き出しだけして reels.json は変えない")
    a = ap.parse_args(argv)

    if a.caption:
        with open(a.caption, encoding="utf-8") as f:
            caption = f.read().strip()
    else:
        caption = M.caption_for(a.dish, a.price)
    if len(caption) > 2200 or caption.count("#") > 30:
        sys.exit("キャプションが長すぎます（%d字・タグ%d個）" % (len(caption), caption.count("#")))

    reels = M.load_reels()
    rid = M.next_id(reels)
    rel = "reels/%s_%s.mp4" % (rid, M.slug(a.slug or a.dish or a.title or "reel"))
    dur = normalize(a.src, os.path.join(ROOT, rel))
    print("できました: %s（%.1f秒・%.1fMB）" % (rel, dur, os.path.getsize(os.path.join(ROOT, rel)) / 1e6))
    if a.dry_run:
        return 0
    reels["posts"][rid] = {"id": rid, "title": a.title or a.dish or rid, "video": rel, "caption": caption}
    reels["order"].append(rid)
    M.save_reels(reels)
    print("reels.json に %s として足しました（順番の最後）" % rid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
