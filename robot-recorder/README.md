# robot-recorder

メイン Windows PC 上の **本線 Recorder** です。映像・センサ・指令ログを集約し、iPad（robotics-hub）へ配信し、記録開始〜終了の間だけ `data_root` に保存します。

`programs/capture_realtime/` は実験用の参考実装です。日常利用は本パッケージを使います。

## 役割

| 役割 | 内容 |
|------|------|
| 受信 | カメラ、Pi からの指令ログ／IMU など |
| 配信 | 低遅延 MJPEG、ステータス API |
| 保存 | Hub の記録開始〜終了のみ（実験フォルダ配下の take） |
| 管理 | 実験フォルダの作成・改名・削除・選択 |

## 実装フェーズ（手順）

### Phase 1（本 README 時点の実装対象）

1. 設定ファイル（`config.example.yaml` / `config.local.yaml`）
2. MJPEG ライブ + JST 時刻焼き込み（日付・時刻・ms）
3. 実験フォルダ CRUD + 「録り込む実験」の選択
4. 記録開始／終了 → take に HLS/mp4 + meta
5. ディスク空き容量チェック（開始時拒否 + 記録中警告）
6. 指令ログ ingest（Pi → Recorder、recording 中のみファイル化）
7. IMU ingest（recording 中のみファイル化）+ `/api/imu/latest`（ライブ暫定）
8. `robotics-hub` の `dev:lab` から本サーバーを起動

### Phase 2（次）

- Hub: 実験管理 UI、記録ボタンを Recorder API に接続
- Pi: 指令成功後に非同期で `/api/ingest/command` へ送信
- IMU ライブを Recorder 経由に完全切替（Socket.IO 中継など）

### Phase 3（その後）

- format_id 別 DataViewer
- センサ種別の追加（足圧など）
- Kaggle 向け書き出し（焼き込みなしは後続検討）

## セットアップ

```bash
cd robot-recorder
copy config.example.yaml config.local.yaml
# data_root などを編集
pip install -r requirements.txt
python -m robot_recorder
```

またはリポジトリの hub から:

```bash
cd robotics-hub
npm run dev:lab
```

## データ配置

`config.local.yaml` の `data_root`（リポジトリ外推奨）:

```text
data_root/
  recorder_state.json
  experiments/
    <experiment_id>/
      experiment.json
      takes/
        <take_id>/
          meta.json
          video.mp4
          commands/servo.jsonl
          sensors/imu.jsonl
```

## 主な API

| 方法 | パス | 説明 |
|------|------|------|
| GET | `/api/status` | 録画・実験・ディスク警告など |
| GET/POST/PATCH/DELETE | `/api/experiments` ... | 実験フォルダ管理 |
| POST | `/api/experiments/{id}/select` | 録り込む実験を選択 |
| POST | `/api/record/start` `/stop` | 記録開始／終了 |
| POST | `/api/ingest/command` | Pi からの指令ログ |
| POST | `/api/ingest/imu` | Pi からの IMU サンプル |
| GET | `/api/imu/latest` | 最新 IMU（ライブ暫定） |
| GET | `/stream.mjpg` | ライブ映像 |

## 設計メモ（議論の確定事項）

- 指令: iPad → Pi（適用時刻を押印）→ 非同期で本 Recorder。失敗時は捨てる（Pi バッファなし）
- IMU 本線: Pi → Recorder → iPad（Phase 2 で Hub 切替）
- 保存は記録ボタン区間のみ。実験名は Hub／API で管理（連番データセット直置きにしない）
- ビュワーは Hub 内で `format_id` ごとに用意（データ同梱必須ではない）
