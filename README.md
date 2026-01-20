# robotics-notes-public

等身大ロボット製作の動画を公開しているYouTubeチャンネル「ゆうきラボ | Yuuki Lab」の公式リポジトリです。

YouTubeチャンネル　→　https://www.youtube.com/@YuukiLab

動画で使用しているツールのプログラムや製作日記を公開しています。

下のリンクのイシューに製作日記をつけています。

https://github.com/yuuki1645/robotics-notes-public/issues/1

<br>

# ディレクトリ解説

## leg-servo-tuner

**【注意】 このディレクトリは更新が止まっています。上位互換のmotion-editor-reactが更新されています。**

サーボの角度を1つずつ調整するFlaskアプリです。

詳細はleg-servo-tunerの [README](leg-servo-tuner/README.md) を参照してください。

## leg-servo-tuner-react

**【注意】 このディレクトリは更新が止まっています。上位互換のmotion-editor-reactが更新されています。**

1つ上のleg-servo-tunerをReactで実装し直したものです。

詳細はleg-servo-tuner-reactの [README](leg-servo-tuner-react/README.md) を参照してください。

## motion-editor-react

Reactで作ったモーションエディタです。

全てのサーボを同時に操作できるので、leg-servo-tuner及びleg-servo-tuner-reactの上位互換です。

現在はこのディレクトリが主に更新されています。

## servo-daemon

ラズパイ上でサーボドライバに直接指令を出すFlaskサーバーです。

leg-servo-tuner、leg-servo-tuner-reactから、このサーバーのAPIを呼び出します。

詳細はservo-daemonの [README](servo-daemon/README.md) を参照してください。

## programs

雑多なプログラム置き場。

最近はほぼ使っていない。
