#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/omeletland-gh/bin:$PATH"
git config user.name  "Kyohei Mikami"  >/dev/null 2>&1
git config user.email "admin@omeletrice.com" >/dev/null 2>&1
echo "============================================"
echo " GitHub にアップロードします"
echo "============================================"
echo
# --- inbox/ の大きな動画は、Mac 標準の avconvert で自動的に小さくする（GitHubは100MB未満） ---
LIMIT=$((90 * 1000 * 1000))
if [ -d inbox ] && command -v avconvert >/dev/null 2>&1; then
  for f in inbox/*.[mM][oO][vV] inbox/*.[mM][pP]4 inbox/*.[mM]4[vV]; do
    [ -f "$f" ] || continue
    size=$(stat -f%z "$f")
    [ "$size" -gt "$LIMIT" ] || continue
    echo "・$(basename "$f") が大きいので小さくしています（数分かかります）…"
    base="${f%.*}"
    done_ok=""
    for preset in PresetHEVC1920x1080 Preset1280x720 Preset960x540; do
      out="${base}_small.mov"
      rm -f "$out"
      if avconvert --source "$f" --output "$out" --preset "$preset" >/dev/null 2>&1 \
         && [ -f "$out" ] && [ "$(stat -f%z "$out")" -le "$LIMIT" ]; then
        # 秒数やメニューの .json はそのまま使えるよう、元の名前に戻す
        mv "$f" "${base}.orig.tmp" && mv "$out" "${base}.mov" && rm -f "${base}.orig.tmp"
        done_ok=1
        echo "  → $(( $(stat -f%z "${base}.mov") / 1000000 ))MB にしました"
        break
      fi
      rm -f "$out"
    done
    if [ -z "$done_ok" ]; then
      echo "  ✗ 小さくできませんでした。この動画は送らずに inbox_保留/ に移します。"
      mkdir -p inbox_保留 && mv "$f" inbox_保留/
    fi
  done
fi
git add -A
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "update $(date +%F_%H%M)" >/dev/null || true
  echo "・変更をまとめました"
fi
echo "・GitHub側の更新を取り込み中…"
git pull --rebase origin main >/dev/null 2>&1 || {
  echo "  取り込みに失敗しました。Claudeに知らせてください。"; read -r -p "Enterで閉じる: " _; exit 1; }
echo "・送信中…（動画と写真があるので1〜2分かかります）"
if git push -u origin main; then
  echo
  echo "✓ 完了しました。Claudeに「あげた」と伝えてください。"
else
  echo
  echo "✗ 失敗しました。上の表示をClaudeに見せてください。"
fi
echo
read -r -p "Enterで閉じる: " _
