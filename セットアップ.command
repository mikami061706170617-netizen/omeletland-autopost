#!/bin/bash
cd "$(dirname "$0")" || exit 1
set -o pipefail
echo "============================================"
echo " Omelet Land 自動投稿 セットアップ"
echo "============================================"
echo

# --- 1. GitHub CLI ---
if ! command -v gh >/dev/null 2>&1; then
  echo "[1/5] GitHub CLI をインストールします…"
  if command -v brew >/dev/null 2>&1; then
    brew install gh || { echo "インストールに失敗しました"; exit 1; }
  else
    echo "Homebrew がありません。https://cli.github.com からインストールしてください。"
    exit 1
  fi
else
  echo "[1/5] GitHub CLI: あり"
fi

# --- 2. ログイン ---
if gh auth status >/dev/null 2>&1; then
  echo "[2/5] GitHub: ログイン済み"
else
  echo "[2/5] GitHubにログインします。ブラウザが開くので承認してください。"
  gh auth login -h github.com -p https -w || exit 1
fi

OWNER=$(gh api user -q .login) || exit 1
REPO="omeletland-autopost"

# --- 3. リポジトリ（公開） ---
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "[3/5] リポジトリ: すでにあります ($OWNER/$REPO)"
else
  echo "[3/5] 公開リポジトリ $OWNER/$REPO を作ります。"
  echo "      ※ 画像とキャプションが公開されます（トークンは公開されません）。"
  read -r -p "      作成してよければ Enter、やめるなら Ctrl+C: " _
  gh repo create "$REPO" --public || exit 1
fi

# --- 4. push ---
echo "[4/5] アップロード中…"
git remote remove origin >/dev/null 2>&1
git remote add origin "https://github.com/$OWNER/$REPO.git" || exit 1
git branch -M main
git push -u origin main || exit 1
echo "      https://github.com/$OWNER/$REPO"

# --- 5. Secrets ---
echo "[5/5] Secrets を登録します。"
echo
python3 get_tokens.py || exit 1

echo
echo "============================================"
echo " 残りは三上さん側（Claude）が実行します。"
echo " このウィンドウは閉じて大丈夫です。"
echo "============================================"
