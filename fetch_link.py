#!/usr/bin/env python3
"""共有リンク（ギガファイル便など）の動画を取り込んで、下見 or リール化する。

GitHub Actions（from_link.yml）から使う。元動画はリポジトリに入れない（作業用の一時フォルダだけ）。
設定は jobs/link.json:
  {"url": "https://xx.gigafile.nu/....",
   "mode": "preview",                # preview=コマ見本だけ作る / render=リールにする
   "clips": {"IMG_1066.MOV": {"reveal": 12.5, "dish": "No.01 ...", "price": 25,
                               "start": 0, "end": 40}}}

preview: preview/<名前>.jpg（2秒ごとのコマ・秒数入り）と preview/info.json を書く
render : clips に書いた動画だけ make_reel でリールにして reels.json に登録する
標準ライブラリのみ（ダウンロードは urllib、編集は ffmpeg）。
"""
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("RAW_DIR", "/tmp/raw")
VIDEO_EXT = (".mov", ".mp4", ".m4v")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/126 Safari/537.36"


def opener():
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.addheaders = [("User-Agent", UA)]
    return op


def save(op, url, referer, dest_dir):
    req = urllib.request.Request(url, headers={"Referer": referer})
    with op.open(req, timeout=600) as r:
        ctype = r.headers.get("Content-Type", "")
        disp = r.headers.get("Content-Disposition", "")
        m = re.search(r"filename\*=UTF-8''([^;]+)", disp) or re.search(r'filename="?([^";]+)', disp)
        name = urllib.parse.unquote(m.group(1)) if m else os.path.basename(urllib.parse.urlparse(url).path)
        if "text/html" in ctype:
            return None, r.read().decode("utf-8", "replace")
        path = os.path.join(dest_dir, name or "download.bin")
        with open(path, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
    return path, None


def download(url):
    """ギガファイル便のページから動画を全部落とす。zip なら展開する。"""
    os.makedirs(WORK, exist_ok=True)
    op = opener()
    page = op.open(url, timeout=60).read().decode("utf-8", "replace")
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
    fid = urllib.parse.urlparse(url).path.strip("/")

    links = []
    for pat in (r"(?:https?://[^\"' ]+)?/dl_zip\.php\?file=[\w\-]+",
                r"(?:https?://[^\"' ]+)?/download\.php\?file=[\w\-]+"):
        for hit in re.findall(pat, page):
            full = hit if hit.startswith("http") else base + hit
            if full not in links:
                links.append(full)
    # まとめてダウンロード(zip)があればそれだけで足りる
    zips = [l for l in links if "dl_zip.php" in l]
    candidates = zips or links or [base + "/download.php?file=" + fid]
    print("候補リンク:", candidates)

    got = []
    for link in candidates:
        path, html = save(op, link, url, WORK)
        if path is None:
            print("HTMLが返りました:", link, html[:300].replace("\n", " "))
            continue
        print("取得:", path, os.path.getsize(path) // 1_000_000, "MB")
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                z.extractall(WORK)
            os.remove(path)
        got.append(path)
    if not got:
        print(page[:2000])
        raise RuntimeError("動画を取得できませんでした（リンクの期限切れか、ページの形式が変わった）")
    vids = []
    for d, _, files in os.walk(WORK):
        for f in files:
            if f.lower().endswith(VIDEO_EXT) and not f.startswith("._"):
                vids.append(os.path.join(d, f))
    return sorted(vids)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration:stream=width,height,codec_name,codec_type",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def preview(vids):
    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    info = {}
    for v in vids:
        name = os.path.basename(v)
        p = probe(v)
        dur = float(p["format"]["duration"])
        step = max(1.0, round(dur / 40, 1))      # 最大40コマ
        out = os.path.join(ROOT, "preview", os.path.splitext(name)[0] + ".jpg")
        vf = ("fps=1/{s},scale=216:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
              ":text='%{{pts\\:hms}}':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,"
              "tile=8x5").format(s=step)
        # pts は fps フィルタ後にずれるので、元の秒数を出すため setpts を先に掛けない
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", v, "-vf", vf, "-frames:v", "1",
                        "-q:v", "4", out], check=True)
        info[name] = {"duration": round(dur, 2), "step": step,
                      "size_mb": round(os.path.getsize(v) / 1e6, 1),
                      "streams": p.get("streams", [])}
        print(name, info[name]["duration"], "秒 → preview/", os.path.basename(out))
    with open(os.path.join(ROOT, "preview", "info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def render(vids, clips):
    import make_reel as M
    by_name = {os.path.basename(v): v for v in vids}
    for name, opts in clips.items():
        if name not in by_name:
            raise RuntimeError("リンクの中に %s がありません（%s）" % (name, ", ".join(by_name)))
        print("\n== %s %s" % (name, json.dumps(opts, ensure_ascii=False)))
        M.make_and_register(by_name[name], dict(opts))


def main():
    job = json.load(open(os.path.join(ROOT, "jobs", "link.json"), encoding="utf-8"))
    vids = download(job["url"])
    print("動画:", [os.path.basename(v) for v in vids])
    if job.get("mode", "preview") == "preview":
        preview(vids)
    else:
        render(vids, job.get("clips", {}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
