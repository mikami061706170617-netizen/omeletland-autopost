# YouTube API 審査の申請（コピペ用）

これを通すと、YouTube に自動で「公開」投稿できるようになります（今は API で上げると非公開に固定）。
**1回の申請で、おとひまチャンネルとオムライス研究所の両方に効きます**（審査は Google Cloud のプロジェクト単位なので、
おとひまで使っている鍵のプロジェクトで申し込みます）。

## 三上さんがやること（15分くらい）

1. パソコンで https://console.cloud.google.com を開き、おとひま用に作ったプロジェクトを選ぶ
   - 左上のプロジェクト名 → 一覧で「**プロジェクト番号**」（数字）をメモ
2. 「APIとサービス」→「OAuth 同意画面」
   - 公開ステータスが「テスト」なら「**アプリを公開**」を押して「本番環境」にする
   - 「プライバシーポリシーのリンク」に下の URL を入れて保存
     `https://github.com/mikami061706170617-netizen/omeletland-autopost/blob/main/PRIVACY.md`
3. 申請フォームを開く: https://support.google.com/youtube/contact/yt_api_form
   - 「**監査と割り当ての拡張（Audit and Quota Extension）**」を選ぶ
   - 下の答えを順にコピペ（英語のまま貼ってください）
4. 画面録画（スマホの画面収録でOK・1分）を YouTube に「限定公開」で上げて、そのリンクをフォームに貼る
   - 映すもの: Actions の画面で「YouTube 投稿」を実行 → YouTube Studio に動画が入ったところ
5. 送信 → Google からの英語のメールが来たら、そのままこのチャットに貼ってください。返事はこちらで書きます。

合格したら、こちらで設定を「全自動」に切り替えます（オムライス研究所用の鍵を1回作るだけ）。

---

## フォームの答え（英語でそのまま貼る）

**Organization name**
```
Omelet Land Tbilisi
```

**Organization website / API client URL**
```
https://github.com/mikami061706170617-netizen/omeletland-autopost
```

**Privacy policy URL**
```
https://github.com/mikami061706170617-netizen/omeletland-autopost/blob/main/PRIVACY.md
```

**Google Cloud project number**
```
（手順1でメモした数字）
```

**Is the API client for internal use only?**
```
Yes. It is used only by the owner to upload our own videos to our own two channels.
```

**Describe your API client / How does it use YouTube API Services?**
```
A small scheduled script (GitHub Actions, Python standard library only) that uploads videos
we produce ourselves to our own YouTube channels once a day:
- "オムライス研究所 三上きょうへい" (cooking videos of our restaurant Omelet Land Tbilisi)
- "おとひまチャンネル" (our family channel)
It only calls videos.insert (resumable upload) and thumbnails.set, with the
youtube.upload scope, authorized once by the channel owner (OAuth 2.0, offline access).
It does not read, collect or display any YouTube data or any other user's data.
Credentials are stored as encrypted GitHub Secrets only.
```

**Which API services / methods**
```
YouTube Data API v3: videos.insert, thumbnails.set
```

**Expected daily quota**
```
About 5-8 uploads per day in total (~1,600 units each) = up to about 13,000 units/day.
We request 20,000 units/day to allow retries.
```

**Why do you need the uploads to be public?**
```
The videos are our own published content (daily Shorts and a weekly long video).
Currently uploads from our unverified project are locked to private, so we must post
manually every day. We would like the scheduled uploads to be published as public.
```

**Do you store or display YouTube data? / Do you share data with third parties?**
```
No. We do not store, cache or display any data obtained from YouTube API Services,
and we do not share any data with third parties.
```

**Do you comply with the YouTube API Services Terms of Service and Developer Policies?**
```
Yes.
```

**Screencast / demo**
```
（手順4で上げた限定公開動画のリンク）
```
