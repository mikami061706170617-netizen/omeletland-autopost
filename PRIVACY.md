# Privacy Policy — Omelet Land Auto Post

Last updated: 2026-09-25

This is the privacy policy for "Omelet Land Auto Post", a small internal tool run by
Omelet Land Tbilisi (Georgia) and the YouTube channel "オムライス研究所 三上きょうへい".
The tool posts our own restaurant videos to our own YouTube, Instagram and Facebook accounts
on a daily schedule. It is not offered to the public and has no other users.

## What data the tool uses
- **Our own videos, titles, descriptions and tags**, which we create and store in this repository.
- **An OAuth refresh token for our own YouTube channel**, used only to upload our videos
  (scope `https://www.googleapis.com/auth/youtube.upload`).

The tool does **not** read, collect or store any data about YouTube viewers or other users.
It does not read comments, analytics, subscriber lists or any other channel's data.

## How data is stored
- Credentials (client secret, refresh token) are stored only as encrypted GitHub Actions Secrets.
  They are never written to the repository or logs.
- Videos and texts are stored in this public repository because they are published content.

## Sharing
We do not sell, share or transfer any data to third parties. Data sent to YouTube is only
the videos and metadata we publish on our own channel.

## YouTube / Google
This tool uses YouTube API Services. By using it you also agree to the
[YouTube Terms of Service](https://www.youtube.com/t/terms) and the
[Google Privacy Policy](http://www.google.com/policies/privacy).
Access can be revoked at any time at
[Google security settings](https://security.google.com/settings/security/permissions).

## Deleting data
Revoking access in the Google security settings removes the tool's access immediately.
We delete the stored token within 7 days of revocation or on request.

## Contact
Omelet Land Tbilisi — contact through the GitHub repository owner
(https://github.com/mikami061706170617-netizen).
