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

実機とつなぐときは、同じリポジトリの **`robot-daemon`** を起動し、ブラウザから API（既定ポート 5000）および必要に応じて Socket.IO（IMU）にアクセスします。**MuJoCo の PPO 学習**（`mujoco-sim` の `train_002_full_actuators`）と併用する場合は、ハブの **「RL 学習テレメトリ」**で Socket.IO（既定 **8791**）経由の観測・行動表示が利用できます。

詳細は [robotics-hub/README.md](robotics-hub/README.md) を参照してください。

## ■ robot-daemon

ラズパイ上でサーボドライバに指令を出すとともに、IMU データを Socket.IO で配信する **Flask + Flask-SocketIO** のサーバーです（REST はサーボ用）。

**[robotics-hub](robotics-hub/)** からこのデーモンの REST API と Socket.IO を利用します（開発・運用の主経路）。

詳細は [robot-daemon/README.md](robot-daemon/README.md) を参照してください。

## ■ 削除済み：旧スタンドアロンのフロントエンド

次のディレクトリは、**[robotics-hub](robotics-hub/)** へ機能を集約したのち、リポジトリから**削除済み**です（重複メンテナンスの解消のため）。  
当時のソースを参照したい場合は、**該当コミットより前の Git 履歴**を辿ってください。

- `leg-servo-tuner`（Flask 版のレッグサーボ調整）
- `leg-servo-tuner-react`
- `motion-editor-react`
- `motion-editor-react-ts`

上記の役割は **robotics-hub** の **レッグサーボ調整**・**モーションエディタ** 等に引き継がれています。手順の詳細は [robotics-hub/README.md](robotics-hub/README.md) を参照してください。

## ■ （更新停止中）programs

雑多なプログラム置き場。

最近はほぼ使っていない。

## ■ mujoco-sim

MuJoCo の脚モデルを **実時間 HTTP サーバ**（`mujoco_realtime_sim`）と **強化学習用環境**（`mujoco_rl_sim`）に分けた Python パッケージ群です。起動例は `python -m mujoco_realtime_sim`。全アクチュエータ学習（`train_002_full_actuators`）では **Socket.IO テレメトリ**（既定ポート **8791**）や **`--step-wall-sleep`** による壁時計の遅延が選べます。**robotics-hub** の RL 学習テレメトリ画面と連携する手順は [mujoco-sim/README.md](mujoco-sim/README.md) を参照してください。

---

※本リポジトリおよびWikiには、Amazonアソシエイトリンクが含まれています。
