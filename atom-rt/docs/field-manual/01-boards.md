# 基板

どちらも ESP32-S3・フラッシュ 8 MB・Grove は **G1=SCL / G2=SDA** です。違うのは中のメモリと、LED・画面・センサです。

## ATOMS3 Lite（いまのファームが想定）

- SoC: **ESP32-S3FN8**（パッケージ内 8 MB フラッシュ、**PSRAM なし**）
- 見た目: 液晶なし。状態は **WS2812（GPIO35）** の 1 ドット
- ボタン: GPIO41
- USB: ネイティブ USB。ファームは `ARDUINO_USB_CDC_ON_BOOT=1` で仮想 COM
- 底面ピン: G5 / G6 / G7 / G8 / G38 / G39

`platformio.ini` のピン（SDA=2、SCL=1、LED=35、ボタン=41）はこの Lite に合わせています。

## ATOM S3R（次の制御中枢）

- SoC: **ESP32-S3-PICO-1-N8R8**（8 MB フラッシュ + **8 MB Octal PSRAM**）
- 0.85 インチ 128×128、BMI270 + BMM150
- Grove は Lite と同じ G1 / G2
- ボタンは同じく GPIO41
- システム RGB は WS2812 ではなく **LP5562**（内部 I2C）。GPIO35 の FastLED はそのままでは点きません

`i2c_foot_proto.h` は「マスターは ATOM S3R」と書いてあります。右足スレーブは別の **ATOMS3 Lite（I2C 0x28）** のまま、という役割分担です。S3R へ焼くときは LED・画面・PSRAM を足す必要があり、今の `rt-usb` を無変更では載せられません。

## フラッシュは「プログラム」と「設定」が別区画

8 MB の SPI フラッシュは、アドレス空間が用途ごとに切れています。Arduino / PlatformIO の典型（概数）:

| オフセット | 領域 | 中身 |
|---|---|---|
| `0x0000` | 2nd bootloader | ROM のあとにアプリを探す |
| `0x8000` | パーティション表 | 以降の切れ目 |
| `0x9000` | **NVS**（約 20 KB） | キー・値。校正と関節経路 |
| `0xE000` | otadata | OTA スロット選択（未使用でも区画はある） |
| `0x10000` | **app** | 今焼いている `rt-usb` |
| 残り | SPIFFS 等 / 未使用 | このファームはファイルシステムを使わない |

このリポジトリは `board_build.flash_size = 8MB` です。専用 `partitions.csv` はまだ置いていないので、**切れ目は Arduino 既定**です。上表は現場用の模式で、バイト数の正本ではありません。

重要なのは次の 2 点だけです。

1. **`pio run -t upload` は app を書き換える。** NVS は通常残る（校正とプロファイルが消えない）。
2. **NVS を消すのは erase / nvs 消去のときだけ。** ボードを「工場出荷の経路」に戻したいときに使う。

## NVS に何が入るか

ESP32 の NVS はフラッシュ上のキー・バリューで、Wear leveling されています。Preferences の名前空間がフォルダに相当します。

| 名前空間 | キー | 意味 |
|---|---|---|
| `jprof` | `n` | 関節数 |
| `jprof` | `r` | `JointRoute` 8 軸ぶん（1 軸 10 バイト） |
| `jprof` | `foot` | `FootRoute` 3 バイト |
| `cal` | `mk0`…`mk7` | その軸のマップが有効か |
| `cal` | `mn0`… | 点数 |
| `cal` | `mx0` / `my0` … | unwrap 角 → 指令角の float 配列 |

再フラッシュせずに配線を変える、というのがプロファイルの存在理由です。マップのキー名は実験リポジトリ `atoms3-as5600-test` の robot ファームと揃えています。Hub の **NVS** タブから実キーを読めます。

## 書き込み

USB CDC を Python が掴んだままでは書けません。

1. `lab_debug.py` / シリアルモニタを閉じる
2. リセットを約 2 秒。**緑 LED が点いたら離す**（ダウンロードモード）
3. `pio run -t upload`

確認は `pio device monitor` ではなく `python tools/rt_usb_log.py`（バイナリなのでモニタは文字化けします）。HELLO の `ver=10` が出れば今のプロトコルです。
