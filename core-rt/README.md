# core-rt

腰の CoreS3 用 20 Hz ファームです。左右の ATOM S3R から CAN で 10 軸と両足を受け、USB でサブ PC へ出します。

USB のフレームとメッセージ番号は [link/include/usb_frame.hpp](../link/include/usb_frame.hpp) です。このボードは **ver 15** です。片脚の ATOM は [atom-rt](../atom-rt/) の `can-leg` です。机上の疎通試験 `can-ping` とは別のファームです。

サブ PC では [link/host/lab_debug.py](../link/host/lab_debug.py) が COM を開きます。操作は robotics-hub の実機テレメトリです。

## 配線

| PaHub | アドレス |
|---|---|
| 右もも | `0x70` |
| 左もも | `0x71` |
| 右すね | `0x72` |
| 左すね | `0x73` |

股とひざのサーボは Grove 直下の 8Servos（`0x26`）。出力 0 が股ロール、1 が股ピッチ、2 がひざです。かかとはすねの 8Servos（`0x25`）の出力 6 と 7 です。右は `0x72` のチャンネル 0、左は `0x73` のチャンネル 5 にあります。足スレーブ（`0x28`）は右がチャンネル 1、左がチャンネル 4 です。センサーのチャンネルは左右で違います。初期値は `src/topology.hpp` です。

校正は論理軸 0〜9（右 0〜4、左 5〜9）に保存します。置き場所はフラッシュ上の NVS 64 KB です。PSRAM と microSD は使いません。

## 書き込み

```text
cd core-rt
pio run -t upload
```

CoreS3 はリセット長押しでダウンロードモードに入ります。`lab_debug.py` が COM を開いたままだと書けません。

ビルドログのボード名は DevKitC-1-N8 のままです。容量の行は 16 MB、アプリは `0x20000` から 3 MB、校正用 NVS は `0x10000` から 64 KB です。PSRAM は使いません。

起動直後は Lab です。PWM は、出した軸だけ動きます。

## I2C スキャン

`src/i2c_scan/main.cpp` は、Grove の 5V を入れてから PaHub の各チャンネルを歩き、応答したアドレスをテキストで出します。結果は 2 秒ごとに繰り返します。モニタを開いたあと、リセットを押さなくても同じ文章が届きます。USB の ver 15 は話しません。総合デバッグはこの間 HELLO を受け取れません。

```text
cd core-rt
pio run -e i2c-scan -t upload
pio device monitor -e i2c-scan

pio run -e core-s3 -t upload
```

最後の 1 行で腰の本線に戻します。`pio run -t upload` は本線のままです。

## チャンネルを開いたまま測る

`src/i2c_hold/main.cpp` は、左もも PaHub `0x71` の CH4 だけを開いたままにします。プローブは、そのポートの黄と黒です。モニタには `hub 71 ch4 open` と、`0x36` の返事の有無が出ます。

```text
cd core-rt
pio run -e i2c-hold -t upload
pio device monitor -e i2c-hold
```

測り終わったら `pio run -e core-s3 -t upload` で腰の本線に戻します。

## CAN 疎通

`src/can_ping/main.cpp` は、PORT.C の Unit CAN で 1 秒ごとに `0x100` を送り、受け取ったフレームをテキストで出します。相手は `atom-rt` の `can-ping`（`0x101`）です。USB の ver 15 は話しません。

机上の 2 台は両方ともバスの端です。120 Ω は両方に付けます。CANH、CANL、絶縁側の G を繋ぎます。Grove の 5V が出ないとユニットは動きません。起動ログの `grove 5V on` を見てください。

```text
cd core-rt
pio run -e can-ping -t upload
pio device monitor -e can-ping
```

相手の `seq` が毎秒増え、`TX ... ok` と `bus=running` が続けば通っています。線を外すと `bus-off` になり、戻すと `running` に戻ります。終わったら `pio run -e core-s3 -t upload` で腰の本線に戻します。
