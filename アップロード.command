#!/bin/bash
# 撮ったオムライス動画を GitHub の「素材置き場」に送る（おとひまと同じしくみ・大きな動画もそのまま）。
# 写真アプリのアルバム「オムライス送る」に入れた動画と、inbox/ に置いた動画を送る。
# 写真（photos/ など）の変更があれば、そのあと GitHub にも送る。
cd "$(dirname "$0")" || exit 1
for d in "$HOME/.local/omeletland-gh/bin" "$HOME/.local/otohima-gh/bin" /opt/homebrew/bin /usr/local/bin; do
  [ -x "$d/gh" ] && export PATH="$d:$PATH"
done
git config user.name  "Kyohei Mikami"  >/dev/null 2>&1
git config user.email "admin@omeletrice.com" >/dev/null 2>&1
echo "============================================"
echo " オムライス動画を送ります"
echo "============================================"
echo
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI(gh)が見つかりません。Claudeに知らせてください。"; read -r -p "Enterで閉じる: " _; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login -h github.com -p https -w || { read -r -p "Enterで閉じる: " _; exit 1; }

# 1) 動画 → 素材置き場（git には入れない）
python3 upload_inbox.py

# 2) 写真などの変更 → GitHub
git add -A
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "update $(date +%F_%H%M)" >/dev/null || true
  echo
  echo "・写真などの変更を送ります…"
  git pull --rebase origin main >/dev/null 2>&1 || {
    echo "  取り込みに失敗しました。Claudeに知らせてください。"; read -r -p "Enterで閉じる: " _; exit 1; }
  if git push -u origin main; then echo "✓ 送りました"; else echo "✗ 失敗しました。上の表示をClaudeに見せてください。"; fi
fi
echo
read -r -p "Enterで閉じる: " _
