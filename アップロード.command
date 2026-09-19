#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/omeletland-gh/bin:$PATH"
git config user.name  "Kyohei Mikami"  >/dev/null 2>&1
git config user.email "admin@omeletrice.com" >/dev/null 2>&1
echo "============================================"
echo " GitHub にアップロードします"
echo "============================================"
echo
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
