#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/omeletland-gh/bin:$PATH"
echo "============================================"
echo " GitHub にアップロードします"
echo "============================================"
echo
git add -A
if [ -n "$(git status --porcelain)" ]; then
  git commit -m "update $(date +%F_%H%M)" || true
fi
echo "送信中…（動画と写真があるので1〜2分かかります）"
if git push -u origin main; then
  echo
  echo "✓ 完了しました。Claudeに「あげた」と伝えてください。"
else
  echo
  echo "✗ 失敗しました。上の表示をClaudeに見せてください。"
fi
echo
read -r -p "Enterで閉じる: " _
