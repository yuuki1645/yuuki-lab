# core-rt

腰の CoreS3 用 20 Hz ファームです。両脚 10 軸と両足を、1 本の Grove I2C で読みます。

USB のフレームとメッセージ番号は [link/include/usb_frame.hpp](../link/include/usb_frame.hpp) です。このボードは **ver 15** です。片脚の ATOM は [atom-rt](../atom-rt/) の ver 14 のままです。

サブ PC では [link/host/lab_debug.py](../link/host/lab_debug.py) が COM を開きます。操作は robotics-hub の実機テレメトリです。

## 配線

| PaHub | アドレス |
|---|---|
| 右もも | `0x70` |
| 左もも | `0x71` |
| 右すね | `0x72` |
| 左すね | `0x73` |

8Servos（`0x25`）はすねのポート 4。出力 0〜4 は股ロール、股ピッチ、ひざ、かかとピッチ、かかとロールです。足スレーブ（`0x28`）はすねのポート 5。左右でポート番号は同じです。

校正は論理軸 0〜9（右 0〜4、左 5〜9）に保存します。置き場所はフラッシュ上の NVS 64 KB です。PSRAM と microSD は使いません。

## 書き込み

```text
cd core-rt
pio run -t upload
```

CoreS3 はリセット長押しでダウンロードモードに入ります。`lab_debug.py` が COM を開いたままだと書けません。

ビルドログのボード名は DevKitC-1-N8 のままです。容量の行は 16 MB、アプリは `0x20000` から 3 MB、校正用 NVS は `0x10000` から 64 KB です。PSRAM は使いません。

起動直後は Lab です。PWM は、出した軸だけ動きます。
