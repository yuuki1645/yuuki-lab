# 地図

いま画面に出ているテレメトリは、ブラウザが ATOM と直接話しているわけではありません。USB を握っているのは PC 上の `lab_debug.py` です。Hub はその通訳です。

## 一列の経路

```text
ATOMS3 Lite / ATOM S3R（予定）
    Grove I2C  100 kHz
      ├ PaHub 0x70     AS5600 × 最大 6
      ├ PaHub 0x71     INA226 / 右足スレーブ
      └ 8Servos 0x25   手前（MUX なし）
        右足 Lite 0x28  DF9-40 四隅
            │
            │ USB CDC  バイナリ ver=10
            ▼
Windows PC  lab_debug.py
            │ Socket.IO :8794
            ▼
ブラウザ     実機テレメトリ（M5）  :5173/m5-telemetry
```

USB の中身は `src/rt_usb/usb_proto.hpp` と `tools/lib/rt_usb_proto.py` が同じ並びです。Socket.IO はその上の JSON（`op: scan` など）で、USB フレームそのものではありません。

## 役割の切り分け

| 層 | 何をするか | 何をしないか |
|---|---|---|
| ファーム `rt-usb` | 20 Hz 制御、I2C、PWM、NVS | Wi-Fi で Hub に出ない |
| `lab_debug.py` | USB 専有、中継、本記録、起動音 | 今後の UI 改善の本線ではない |
| Hub `/m5-telemetry` | 機体（右脚）の操作と表示 | ATOM の COM を直接開かない |
| Hub `/atom-bench` | 机上 1 サーボの校正・単体テスト | 機体の記録・カメラは持たない |

ファームは **1 本**（PlatformIO 環境 `rt-usb`）です。机上と機体の違いは USB コマンドの **Lab / Robot** で、スケッチの切り替えではありません。
