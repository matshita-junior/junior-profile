# junior-profile

松下哲也ジュニアの自己紹介サイト。HTML・CSS・JavaScriptのみで動作し、ビルドや外部依存関係は不要です。

## ローカルで確認

```sh
cd /workspace/junior-profile
python3 -m http.server 4173 --bind 0.0.0.0
```

ブラウザでポート4173に接続します。`index.html` が文章・プロフィール、`styles.css` がデザイン、`script.js` がフッターの年表示です。経歴やSNSリンクは確認できる情報を追加してください。

## HamCup MV

`hamcup/` はHamCupのじゃが・さくら・まんじゅうによる縦型（9:16）30秒のミュージックビデオ「今日も、よく帰ってきたね ― おやすみのお茶 ―」です。ローカルでは `http://localhost:4173/hamcup/` で再生できます。

- `hamcup/index.html`：居間の舞台（SVG）、プレイヤー、歌詞・映像構成
- `hamcup/mv.js`：タイムライン（カメラ・キャラの動き・テロップ）と、Web Audio APIによるローファイ・ポップの演奏
- `hamcup/mv.css`：ページと書き出しモードの見た目
- `hamcup/assets/`：キャラクターシートから切り出したキャラ・カップの画像（笑顔・あくびは表情パーツを合成）
- `hamcup/tools/export-mv.js`：MP4（1080×1920 / 30fps）への書き出し

キャラの動きやカメラは `mv.js` の `renderA`（0〜7秒）・`renderB`（7〜30秒）と `CAM_B`、歌詞の表示時間は `LYRICS`、曲は `BARS`・`PIANO_LINE`・`HUM` で変更できます。サビのメロディはハミングのガイドなので、歌声は別途収録した音声に差し替えてください。

### MP4に書き出す

Node.js・Playwright（Chromium）・ffmpeg が必要です。

```sh
python3 -m http.server 4173          # リポジトリ直下で起動
node hamcup/tools/export-mv.js hamcup-mv.mp4
```

## 公開

静的サイトとして、リポジトリ直下を公開ディレクトリに指定します。ビルドコマンドは不要です。`index.html`、`styles.css`、`script.js`、`favicon.svg`、`hamcup/` フォルダーを一緒に配信してください。サブパスでの配信にも対応しています。

GitHub Pagesを利用する場合は、サイトのファイルを対象ブランチへ反映後、リポジトリの Settings → Pages でそのブランチのルートを選択します。公開設定の変更にはGitHub側の権限が必要です。

### このリポジトリでの公開手順

1. 作成したファイルとREADMEの変更をコミットし、`matshita-junior/junior-profile` の `nakatsu-post-ai` ブランチへ反映します。Codexの変更をPRで反映する場合は、そのブランチをマージ先に指定してください。
2. GitHubでリポジトリを開き、**Settings → Pages** を選択します。
3. **Build and deployment → Source** を **Deploy from a branch** に設定します。
4. **Branch** に **nakatsu-post-ai**、フォルダーに **/(root)** を選び、**Save** を押します。
5. GitHubのデプロイ完了を待ち、Pages画面に表示される公開URLを開きます。通常のURLは `https://matshita-junior.github.io/junior-profile/` です。
6. 名前、仕事、趣味、活動の表示、ページ内リンク、スマートフォン表示を確認してください。

Pages設定にはリポジトリの管理権限が必要です。非公開リポジトリの場合は、GitHubプランがPagesに対応している必要があります。掲載内容は名前、呼び名、仕事、趣味、活動、メッセージのみで、SNS・年齢・住所・勤務先・連絡先は含めていません。
