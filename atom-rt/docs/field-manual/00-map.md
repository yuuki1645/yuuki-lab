# 地図

いま画面に出ているテレメトリは、ブラウザが ATOM と直接話しているわけではありません。USB を握っているのは PC 上の `lab_debug.py` です。Hub はその通訳です。iPad も PC の Chrome も、同じ :8794 に乗るクライアントです。

## 一列の経路

```text
ATOMS3 Lite / ATOM S3R（予定）
    Grove I2C  100 kHz
      ├ PaHub 0x70     AS5600 × 最大 6
      ├ PaHub 0x71     INA226 / 右足スレーブ
      └ 8Servos 0x25   手前（MUX なし）
        右足 Lite 0x28  DF9-40 四隅
            │
            │ USB CDC  バイナリ ver=14
            │  中身は AA 55 で始まるフレーム。ASCII ではない
            ▼
Windows PC  lab_debug.py
            │ Socket.IO :8794  （JSON。USB フレームそのものではない）
            ▼
ブラウザ     実機テレメトリ /atom-bench  :5173
```

USB の中身は `src/rt_usb/usb_proto.hpp` と `tools/lib/rt_usb_proto.py` が同じ並びです。Socket.IO はその上の JSON（`op: scan` など）で、ATOM にはバイナリだけが届きます。

## 役割の切り分け

| 層 | 何をするか | 何をしないか |
|---|---|---|
| ファーム `rt-usb` | 20 Hz 制御、I2C、PWM、NVS | Wi-Fi で Hub に出ない。COM を複数プロセスで分けない |
| `lab_debug.py` | USB 専有、中継、本記録、起動音、イベント 5000 行 | 今後の UI 改善の本線ではない |
| Hub `/m5-telemetry` | 機体（右脚）の操作と表示 | ATOM の COM を直接開かない |
| Hub `/atom-bench` | 机上 1 サーボの校正・単体テスト | 機体の記録・カメラは持たない |

ファームは **1 本**（PlatformIO 環境 `rt-usb`）です。机上と機体の違いは USB コマンドの **Lab / Robot** と、関節の **有効マスク** です。スケッチの切り替えではありません。

## 画面の置き場

| 場所 | 何があるか |
|---|---|
| 机上ラボの左 | トポロジ。どのタブでも配線と磁石を見られる |
| 下端のステータスバー | 接続・USB ver・モード・PWM・指令・生角・電源・周期・I2C 増分 |
| 下端のドック | イベント。新しい行が下。一時停止して読める |
| プロファイルタブ | 経路（残す）と有効（切る）。ボードへ送信で NVS へ |
| NVS タブ | フラッシュ上の実キー。空欄は「未読取」と「キー無し」を取り違えない |
| URL | `?tab=profile` などでタブを残す。手帳は `#manual/usb` |

ステータスバーの USB 番号は HELLO の `ver` です。有効マスクは **ver 13 以上** が必要です。いま焼いている正本は **ver 14** です。
