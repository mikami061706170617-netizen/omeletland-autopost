#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mac用: 撮ったオムライス動画を GitHub のリリース「素材置き場(sozai)」に送る(アップロード.command から呼ばれる)。
おとひまと同じしくみ。git には入らないので、大きな動画(〜2GB)も小さくせずにそのまま送れる。

送る動画の入れかたは2つ:
  ① いちばんかんたん: 写真アプリのアルバム「オムライス送る」に動画を入れておく
     → 1本ずつ写真アプリから取り出して送り、すぐ消す(Macの容量をほとんど使わない)
     → 送った動画は inbox/.sent_ids.txt に記録して、二度送らない(アルバムはそのままでOK)
  ② inbox/ フォルダに動画ファイルを入れておく

- ファイル名を「撮影日_時刻_長さ_もとの名前」に変える
- 送れた動画は Mac から消す(写真アプリ・iCloud の元の動画はそのまま)
- 最後に Actions の「素材の下見(sozai.yml)」を動かす → コマ見本ができ、Claude がパカーンの瞬間を選んで編集する
リポジトリは Public なので、素材置き場の動画は編集が終わったら Actions がすぐ消す。
"""

import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"
REPO = "mikami061706170617-netizen/omeletland-autopost"
TAG = "sozai"
EXT = {".mov", ".mp4", ".m4v"}
NAMED = re.compile(r"^\d{4}-\d\d-\d\d_\d{4}_\d+s_")
ALBUM = "オムライス送る"
SENT_IDS = INBOX / ".sent_ids.txt"


def sh(*args, check=True):
    p = subprocess.run(list(args), capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[-300:])
    return p.stdout.strip()


def mdls(path, key):
    try:
        out = sh("mdls", "-raw", "-name", key, str(path), check=False)
    except FileNotFoundError:       # Mac 以外
        return None
    return None if not out or out == "(null)" else out


def shot_time(path):
    """撮影日時(写真アプリの書き出しなら作成日=撮影日)。なければファイルの日時。"""
    raw = mdls(path, "kMDItemContentCreationDate")
    if raw:
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z").astimezone()
        except ValueError:
            pass
    st = path.stat()
    return datetime.fromtimestamp(min(st.st_mtime, getattr(st, "st_birthtime", st.st_mtime)))


def seconds(path):
    raw = mdls(path, "kMDItemDurationSeconds")
    try:
        return int(float(raw)) if raw else 0
    except ValueError:
        return 0


def ensure_release(tag, title, notes):
    if sh("gh", "release", "view", tag, "--repo", REPO, check=False) == "":
        sh("gh", "release", "create", tag, "--repo", REPO, "--title", title,
           "--notes", notes, "--prerelease", check=False)


LIMIT = 1_900_000_000      # GitHub のリリースは1本2GBまで


def shrink(p):
    """2GBを超える動画だけ、Mac 標準の avconvert で 1080p(HEVC)にする。"""
    out = p.with_name(p.stem + "_1080.mov")
    print(f"   {p.name} が 2GB を超えているので小さくしています(数分かかります)…", flush=True)
    subprocess.run(["avconvert", "--source", str(p), "--output", str(out),
                    "--preset", "PresetHEVC1920x1080"], capture_output=True)
    if out.is_file() and out.stat().st_size <= LIMIT:
        p.unlink()
        return out
    out.unlink(missing_ok=True)
    print("   ✗ 小さくできませんでした。撮影を2つに分けてもらえると送れます。")
    return None


def send_one(p, when=None):
    """動画1本を素材置き場に送って、Macから消す。送れたら True。"""
    name = p.name
    if not NAMED.match(name):
        t = when or shot_time(p)
        name = f"{t:%Y-%m-%d_%H%M}_{seconds(p)}s_{p.name}"
    name = re.sub(r"[^\w.\-ぁ-んァ-ヶ一-龠ー]", "_", name)
    up = p.with_name(name)
    if up != p:
        p.rename(up)
    if up.stat().st_size > LIMIT:
        up = shrink(up)
        if up is None:
            return False
    print(f"   {name}({up.stat().st_size / 1e6:.0f}MB)送信中…", flush=True)
    try:
        sh("gh", "release", "upload", TAG, str(up), "--repo", REPO, "--clobber")
    except RuntimeError as e:
        print(f"   ✗ 失敗しました: {e}")
        return False
    up.unlink()          # 送れたら消す(元の動画は写真アプリに残っている)
    return True


def send_inbox():
    rest = sorted(p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in EXT)
    sent = 0
    for i, p in enumerate(rest, 1):
        print(f"[inbox {i}/{len(rest)}]")
        sent += send_one(p)
    return sent


# ---------------------------------------------------------------- 写真アプリのアルバムから

def photos(script):
    """写真アプリに AppleScript で頼む。"""
    p = subprocess.run(["osascript", "-"], input=script, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[-300:])
    return p.stdout.strip()


def album_items():
    out = photos(f'''
tell application "Photos"
  if not (exists album "{ALBUM}") then make new album named "{ALBUM}"
  set out to ""
  repeat with m in (media items of album "{ALBUM}")
    set d to ""
    try
      set d to ((date of m) as «class isot» as string)
    end try
    set out to out & (id of m) & tab & (filename of m) & tab & d & linefeed
  end repeat
  return out
end tell''')
    items = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and Path(parts[1]).suffix.lower() in EXT:
            try:
                when = datetime.fromisoformat(parts[2])
            except ValueError:
                when = None
            items.append((parts[0], parts[1], when))
    items.sort(key=lambda x: x[2] or datetime.max)
    return items


WORK = Path.home() / "Pictures" / "オムライス送信中"   # 写真アプリが確実に書き込める場所


def _wait_files(dst, sec):
    """書き出しが終わるまで待つ(ファイルの大きさが止まるまで)。"""
    last = None
    for _ in range(sec):
        files = [p for p in Path(dst).rglob("*") if p.is_file() and not p.name.startswith(".")]
        sizes = tuple(sorted((p.name, p.stat().st_size) for p in files))
        if files and sizes == last:
            return files
        last = sizes
        time.sleep(1)
    return [p for p in Path(dst).rglob("*") if p.is_file() and not p.name.startswith(".")]


def export_one(mid, dst):
    """写真アプリから動画を1本書き出す。今の版 → だめならオリジナル の順にためす。"""
    errors = []
    for originals in (False, True):
        opt = " with using originals" if originals else ""
        try:
            photos(f'''
tell application "Photos"
  with timeout of 3600 seconds
    export {{media item id "{mid}"}} to (POSIX file "{dst}" as alias){opt}
  end timeout
end tell''')
        except RuntimeError as e:
            errors.append(str(e))
        files = _wait_files(dst, 60)
        vids = [p for p in files if p.suffix.lower() in EXT]
        if vids:
            return max(vids, key=lambda p: p.stat().st_size)
        if files:
            errors.append("動画ではないファイルが出てきました: " + ", ".join(p.name for p in files))
            for p in files:
                p.unlink()
    raise RuntimeError("写真アプリから動画を取り出せませんでした" +
                       (f"({' / '.join(errors)[-300:]})" if errors else
                        "(iCloud から動画を取ってこられなかったのかもしれません)"))


def send_album():
    try:
        items = album_items()
    except (RuntimeError, FileNotFoundError) as e:
        print(f"(写真アプリのアルバム「{ALBUM}」は使えませんでした: {e})")
        return 0
    done = set(SENT_IDS.read_text().split()) if SENT_IDS.is_file() else set()
    todo = [it for it in items if it[0] not in done]
    if not todo:
        print(f"写真アプリのアルバム「{ALBUM}」に、まだ送っていない動画はありません")
        return 0
    print(f"写真アプリのアルバム「{ALBUM}」から {len(todo)}本 送ります(1本ずつ取り出して、送ったら消します)")
    sent, fails = 0, 0
    WORK.mkdir(parents=True, exist_ok=True)
    for i, (mid, fname, when) in enumerate(todo, 1):
        print(f"[アルバム {i}/{len(todo)}] {fname} を写真アプリから取り出し中…", flush=True)
        tmp = Path(tempfile.mkdtemp(prefix="omurice-", dir=WORK))
        try:
            p = export_one(mid, tmp)
            if send_one(p, when):
                sent += 1
                fails = 0
                with open(SENT_IDS, "a") as f:
                    f.write(mid + "\n")
        except RuntimeError as e:
            print(f"   ✗ 失敗しました: {e}")
            fails += 1
            if fails >= 3 and sent == 0:
                print("\n3本つづけて取り出せなかったので、いったん止めます。この画面をClaudeに見せてください。")
                break
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    return sent


def main():
    ensure_release(TAG, "素材置き場", "撮ったオムライス動画(編集が終わったら自動で消えます)")
    sent = send_inbox() + send_album()
    if not sent:
        print(f"\n送る動画がありませんでした。写真アプリのアルバム「{ALBUM}」に動画を入れてから、もう一度押してね。")
        return
    print(f"\n✓ {sent}本 送りました。送った動画は Mac から消したので、容量は元にもどっています。")
    if sent:
        sh("gh", "workflow", "run", "sozai.yml", "--repo", REPO, check=False)
        print("下見を作りはじめました。Claude がパカーンの瞬間を選んで、リールと YouTube ショートにします。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"✗ うまくいきませんでした: {e}\nこの画面をClaudeに見せてください。")
        sys.exit(1)
