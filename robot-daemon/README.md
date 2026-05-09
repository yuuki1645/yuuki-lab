# robot-daemon

ラズベリーパイ等で動かす **ロボット側デーモン**です。サーボ指令は **REST API**、IMU（MPU6050）ストリームは **Socket.IO** で **robotics-hub** などのフロントから利用します。

以前の **`servo-daemon`** ディレクトリから改名したもので、REST のサーボ API に加え IMU 連携が入っています。

## 機能概要

- **HTTP（Flask）**: `/servos`, `/set`, `/set_multiple`, `/transition` など（`rest_servo.py`）
- **Socket.IO**: IMU 姿勢データの配信・ライフサイクル（`imu_stream_service.py`, `socketio_lifecycle.py`）
- **既定ポート**: **5000**（`app.py` の `socketio.run(..., port=5000)`）

## 起動

リポジトリ直下の **`robot-daemon`** をカレントにして:

```bash
cd robot-daemon
python app.py
```

- 待ち受け: `0.0.0.0:5000`（同一 LAN から他端末のブラウザ経由でアクセスしやすい設定）
- HTTP アクセスログを出したいとき: `python app.py --access-log`

## 依存関係（例）

標準的には次のような Python パッケージが必要です（環境に合わせて `pip install` してください）。

- `flask`, `flask-cors`, `flask-socketio`
- 実機の MPU6050 を読む場合: `smbus2`

IMU が無い／開発時は `imu.py` のモック経由で動く構成にもなっています。

## フロント側との対応

**[robotics-hub](../robotics-hub/)** の `src/shared/constants.ts` にある **`SERVO_DAEMON_URL`**（実質 robot-daemon のベース URL）が、このプロセスのオリジン（通常は `http://<ホスト名>:5000`）を指します。変数名は歴史的なものですが、接続先は **robot-daemon** です。

同一マシンで **[iphone-camera-relay](../iphone-camera-relay/)** など別サービスをポート **5000** で動かす場合は、どちらかのポートをずらす必要があります。
