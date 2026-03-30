# yuuki-lab

等身大ロボット製作の動画を公開しているYouTubeチャンネル「ゆうきラボ | Yuuki Lab」の公式リポジトリです。

YouTubeチャンネル　→　https://www.youtube.com/@YuukiLab

動画で使用しているツールのプログラムや製作日記を公開しています。

下のリンクのイシューに製作日記をつけています。

https://github.com/yuuki1645/robotics-notes-public/issues/1

<br>

# ディレクトリ解説

## ■ robotics-hub（メイン）

**フロントエンドの中心となる作業場所です。** モーションエディタ、レッグサーボ調整など複数ツールを 1 つの Vite + React + TypeScript アプリにまとめています。

実機とつなぐときは、同じリポジトリの **`servo-daemon`** を起動し、ブラウザから API（既定ポート 5000）にアクセスします。

詳細は [robotics-hub/README.md](robotics-hub/README.md) を参照してください。

## ■ servo-daemon

ラズパイ上でサーボドライバに直接指令を出す Flask サーバーです。

**[robotics-hub](robotics-hub/)** からこのサーバーの API を呼び出します（開発・運用の主経路）。

詳細は [servo-daemon/README.md](servo-daemon/README.md) を参照してください。

## ■ （更新停止・レガシー）leg-servo-tuner

サーボの角度を 1 つずつ調整する Flask アプリです。相当機能は **robotics-hub** のレッグサーボ調整にあります。

詳細は [leg-servo-tuner/README.md](leg-servo-tuner/README.md) を参照してください。

## ■ （更新停止・レガシー）leg-servo-tuner-react

`leg-servo-tuner` を React で実装したものです。相当機能は **robotics-hub** にあります。

詳細は [leg-servo-tuner-react/README.md](leg-servo-tuner-react/README.md) を参照してください。

## ■ （更新停止・レガシー）motion-editor-react

React で作ったモーションエディタです。後継の TypeScript 版や **robotics-hub** に流れを寄せています。

詳細は [motion-editor-react/README.md](motion-editor-react/README.md) を参照してください。

## ■ （更新停止・レガシー）motion-editor-react-ts

`motion-editor-react` を TypeScript で作り直したものでした。**機能は [robotics-hub](robotics-hub/) のモーションエディタへ移行済み**であり、日常的な開発の中心ではありません（参照・履歴用）。

詳細は [motion-editor-react-ts/README.md](motion-editor-react-ts/README.md) を参照してください。

## ■ （更新停止中）programs

雑多なプログラム置き場。

最近はほぼ使っていない。
