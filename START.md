# これを読んだら、この通りに実行してください

このフォルダは Omelet Land Tbilisi のインスタ/FB自動投稿一式です。
ここ以外のフォルダは絶対に触らないでください（AI CADとは無関係です）。
README.md と CLAUDE.md と SETUP.md も読んでから、次を順にやってください。

1. mkdir -p .github/workflows && mv daily.yml .github/workflows/daily.yml
2. python3 test_logic.py が全部通ることを確認
3. git init してコミット
4. gh が無ければ brew install gh、未認証なら gh auth login
5. gh repo create omeletland-autopost --public --source=. --push
6. images/d04.jpg の raw URL に curl -sI して 200 が返ることを確認
7. ここでいったん止まって私に知らせてください。私が python3 get_tokens.py を実行します。
   終わったら gh secret list で IG_USER_ID / FB_PAGE_ID / PAGE_TOKEN の3つを確認
8. gh workflow run daily.yml -f dry_run=true で試し、gh run watch で結果を見る
9. 問題なければ gh workflow run daily.yml で本番投稿（D04＝シェフの物語）
10. 出た Instagram と Facebook のリンクを見せて、git pull で state.json の記録を確認
