#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo " Omelet Land 自動投稿 セットアップ"
echo "============================================"
echo

GH_HOME="$HOME/.local/omeletland-gh"

# --- 1. GitHub CLI ---
if command -v gh >/dev/null 2>&1; then
  echo "[1/5] GitHub CLI: あり"
elif [ -x "$GH_HOME/bin/gh" ]; then
  export PATH="$GH_HOME/bin:$PATH"
  echo "[1/5] GitHub CLI: あり（前回ダウンロードしたもの）"
else
  echo "[1/5] GitHub CLI をダウンロードします（Homebrewは使いません）…"
  case "$(uname -m)" in arm64) A=arm64 ;; *) A=amd64 ;; esac
  VER=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["tag_name"].lstrip("v"))') || VER=""
  [ -n "$VER" ] || { echo "  バージョン取得に失敗しました"; read -r -p "Enterで閉じる"; exit 1; }
  TMP=$(mktemp -d) || exit 1
  echo "      gh ${VER} (${A}) を取得中…"
  if curl -fsSL -o "$TMP/gh.zip" "https://github.com/cli/cli/releases/download/v${VER}/gh_${VER}_macOS_${A}.zip"; then
    unzip -q -o "$TMP/gh.zip" -d "$TMP/x"
  elif curl -fsSL -o "$TMP/gh.tgz" "https://github.com/cli/cli/releases/download/v${VER}/gh_${VER}_macOS_${A}.tar.gz"; then
    mkdir -p "$TMP/x" && tar xzf "$TMP/gh.tgz" -C "$TMP/x"
  else
    echo "  ダウンロードに失敗しました"; read -r -p "Enterで閉じる"; exit 1
  fi
  SRC=$(find "$TMP/x" -type d -name bin -maxdepth 3 | head -1)
  [ -n "$SRC" ] || { echo "  展開に失敗しました"; read -r -p "Enterで閉じる"; exit 1; }
  rm -rf "$GH_HOME"; mkdir -p "$GH_HOME"
  cp -R "$(dirname "$SRC")"/* "$GH_HOME"/
  chmod +x "$GH_HOME/bin/gh"
  xattr -dr com.apple.quarantine "$GH_HOME" 2>/dev/null
  rm -rf "$TMP"
  export PATH="$GH_HOME/bin:$PATH"
  gh --version >/dev/null 2>&1 || { echo "  ghが動きません"; read -r -p "Enterで閉じる"; exit 1; }
  echo "      インストールできました: $(gh --version | head -1)"
fi

# --- 2. ログイン ---
if gh auth status >/dev/null 2>&1; then
  echo "[2/5] GitHub: ログイン済み"
else
  echo "[2/5] GitHubにログインします。ブラウザが開くので承認してください。"
  gh auth login -h github.com -p https -w || { read -r -p "Enterで閉じる"; exit 1; }
fi

OWNER=$(gh api user -q .login) || { read -r -p "Enterで閉じる"; exit 1; }
REPO="omeletland-autopost"

# --- 3. リポジトリ（公開） ---
if gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
  echo "[3/5] リポジトリ: すでにあります ($OWNER/$REPO)"
else
  echo "[3/5] 公開リポジトリ $OWNER/$REPO を作ります。"
  echo "      ※ 画像とキャプションが公開されます（トークンは公開されません）。"
  read -r -p "      作成してよければ Enter、やめるなら Ctrl+C: " _
  gh repo create "$REPO" --public || { read -r -p "Enterで閉じる"; exit 1; }
fi

# --- 4. push ---
echo "[4/5] アップロード中…"
git remote remove origin >/dev/null 2>&1
git remote add origin "https://github.com/$OWNER/$REPO.git"
git branch -M main
gh auth setup-git >/dev/null 2>&1
git push -u origin main || { read -r -p "Enterで閉じる"; exit 1; }
echo "      https://github.com/$OWNER/$REPO"

# --- 5. Secrets ---
echo "[5/5] Secrets を登録します。"
echo
python3 get_tokens.py

echo
echo "============================================"
echo " 終わりました。このウィンドウは閉じて大丈夫です。"
echo "============================================"
read -r -p "Enterで閉じる: " _
