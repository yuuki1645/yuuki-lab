# robot-daemon

ラズベリーパイ等で動かす **ロボット側デーモン**です。サーボ指令は **REST API**、IMU（MPU6050）ストリームは **Socket.IO** で **robotics-hub** などのフロントから利用します。

以前の **`servo-daemon`** ディレクトリから改名したもので、REST のサーボ API に加え IMU 連携が入っています。

## 機能概要

- **HTTP（Flask）**: `/servos`, `/set`, `/set_multiple`, `/transition` など（`rest_servo.py`）
- **Socket.IO**: IMU 姿勢データの配信・ライフサイクル（`imu_stream_service.py`, `socketio_lifecycle.py`）
- **IMU CSV ログ**（任意）: ストリーミング中のサンプルをメモリに溜め、一定間隔で CSV 追記（`imu_csv_log.py`）
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

### IMU の CSV ログ（ラズパイでの解析用）

`imu/start` でストリーミングが始まると、**セッションごと**に `IMU_LOG_DIR` 以下へ `imu_YYYYMMDD_HHMMSS.csv` を作成し、サンプルをメモリに蓄えます。**約 `IMU_LOG_FLUSH_SEC` 秒ごと**にバッファをファイルへ追記し、`imu/stop` や読み取りエラーでストリームが止まったときに**残りをすべて書き出します**。

| 環境変数 | 説明 |
|----------|------|
| `IMU_LOG_DISABLE` | `1` / `true` などで **CSV を出さない** |
| `IMU_LOG_DIR` | 出力ディレクトリ（既定: `./imu_logs`、相対パスはカレント基準） |
| `IMU_LOG_FLUSH_SEC` | ディスクへのフラッシュ間隔（秒、既定: **10**、最小 0.5） |

列は `wall_unix`, `perf_timestamp`, `mock`, 加速度・角速度・推定角（`imu/sample` と同じ構造をフラット化）です。

## フロント側との対応

**[robotics-hub](../robotics-hub/)** の `src/shared/constants.ts` にある **`SERVO_DAEMON_URL`**（実質 robot-daemon のベース URL）が、このプロセスのオリジン（通常は `http://<ホスト名>:5000`）を指します。変数名は歴史的なものですが、接続先は **robot-daemon** です。

同一マシンで **[iphone-camera-relay](../iphone-camera-relay/)** など別サービスをポート **5000** で動かす場合は、どちらかのポートをずらす必要があります。

### Robotics Hub のテレメトリページ

**[robotics-hub](../robotics-hub/)** の **テレメトリ**（`/telemetry`）は、ブラウザから本デーモンへ Socket.IO で接続し、接続直後に **`imu/start`**（既定 30 Hz）を送ります。サーバー側は従来どおり **`imu/sample`** で加速度・角速度・推定角をブロードキャストします（実装は `imu_stream_service.py`）。Hub を別マシンのブラウザで開く場合は、デーモンが `0.0.0.0:5000` で待ち受けていることと、Hub 側の **`VITE_TELEMETRY_IMU_SOCKET_URL`**（または同一 LAN なら既定の `hostname:5000`）を確認してください。
