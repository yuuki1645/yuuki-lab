# ファーム

環境名は `rt-usb`。入口は `src/rt_usb/main.cpp` だけです。Wi-Fi はありません。プロトコル番号は `kUsbFwVer`（いま **14**）です。Python の `FW_VER` と揃えます。

## 二つのコア

ESP32-S3 は LX7 が 2 つあります。このファームは仕事を分けます。

| コア | 仕事 | 触ってよいもの |
|---|---|---|
| **Core 1** | 50 ms（20 Hz）制御ループ | I2C、サーボ PWM、スナップショット書き込み |
| **Core 0** | USB の組み立てと送信 | スナップショットのコピー。**I2C は触らない** |

I2C と USB を同じコアでやると、CDC の待ちで周期が壊れます。SCAN や PROBE は Core 1 が I2C を使うので、その周期は伸びます（overrun の主因）。NVS の読み書きは Core 0 がフラッシュを触るので、そのあいだテレメトリも詰まりやすいです。

ループの中身:

1. 要求があれば SCAN / PROBE
2. **有効かつアドレスがある**関節の AS5600（角度・磁石・AGC）
3. 同じ条件の INA226（V / A / W）
4. 右足が有効ならスレーブの四隅 mV
5. 校正マップがあれば unwrap → 指令角
6. Robot なら 135°、Lab なら手動角
7. `out_mask` とアクチュエータ経路と有効マスクで PWM
8. Snapshot を Core 0 へ

政策（RL）はまだ空です。Robot は Hold です。後から `selectAction` を差し替える想定です。

無効にした関節は I2C を叩きません。経路（hub / addr）は NVS に残ります。机上で機体プロファイルを消さずに、未配線の軸だけ黙らせるためです。

AS5600 は一度失敗するとその周期では諦めます。INA は欠測しても枠を残して再試行します。イベントに `i2c skip jointN (disabled)` と `AS5600 give up` が並ぶときは、まず有効マスクと実配線を見てください。

## Lab と Robot

| モード | PWM | 政策 | 用途 |
|---|---|---|---|
| **Lab**（焼いた直後） | 明示するまでオフ | 許可軸だけの手動角 | 机。挿抜・磁石 |
| **Robot** | 全軸オン | 135° | 機体、従来の `rt_monitor` |

LED（Identify 中以外）:

- 青っぽい … Lab かつ PWM オフ
- 緑 … センサ OK でループに余裕
- 赤点滅 … AS5600 が読めていない
- 赤 … overrun、または Robot なのに 8Servos なし
- 虹色 … Identify、または本体ボタン

可動域は **40〜230°**（RDS51150、500〜2500 µs = 0〜270° のうち安全側）。INA が約 **8 A** を超えると全 PWM オフ。

## バージョン（現場で見る番号）

HELLO の 1 バイト目です。Hub のステータスバーと同じです。

| ver | 入れたもの |
|---|---|
| 10 | 8 関節テレメトリ 316 B。旧 ASCII とは話せない |
| 12 | ProfPut 末尾に有効マスク 2 バイト。NVS blob `en` |
| 13 | マスク無し PUT は拒否。ProfOk は `en` の読み戻し後。USB リセット抑制 |
| **14** | NVS 一覧を間隔付きで送る。TX バッファ拡大。値の全文はまだ CDC を殺しうる |

机上で有効チェックを使うなら **13 以上**。NVS タブを触るなら **14** を焼いてください。Python 側も同じ番号です。古い `lab_debug.py` のまま新しいボードを掴むと、PUT の長さが足りずチェックが戻ります。

## ソースの地図

| ファイル | 役割 |
|---|---|
| `src/rt_usb/main.cpp` | ループ、USB 受信状態機械、NVS、校正スイープ |
| `src/rt_usb/usb_proto.hpp` | フレームとペイロード（`kUsbFwVer`） |
| `src/rt_usb/snapshot.hpp` | Core 間の 1 周期データ。関節 8・INA 8 |
| `src/rt_usb/joint_profile.hpp` | `JointRoute` / `FootRoute` / 有効マスク |
| `src/as5600.hpp` | 角度・STATUS・AGC |
| `src/robot/pahub.hpp` | PCA9548A |
| `src/robot/ina226.hpp` | Unit INA226 |
| `src/robot/i2c_foot_proto.h` | 右足スレーブのレジスタ |

`src/robot/` の `.cpp` はコンパイルしません。ヘッダだけ共有しています。

## 関節プロファイル

論理関節 `0..7` が、実際の I2C / サーボ ch を指します。机の配線と機体が違っても **再フラッシュ不要** です。

既定（機体の典型）:

- サーボ: Grove 直結の 8Servos `0x25` の ch `i`
- 関節 0〜5 の AS5600: PaHub `0x70` CH`i`（アドレス `0x36`）
- 関節 6〜7 のエンコーダ: 未割当（`enc_addr=0`）
- INA: 関節 0〜1 だけ PaHub `0x71` CHi（`0x41`）。以降は SCAN から足す
- 右足: `0x71` CH2 / `0x28`。`addr=0` で読まない

`hub=0` は Grove 直結（MUX なし）。そのとき `ch` は `-1` です。

有効マスクは経路とは別です。bit0 が関節 0。`jen=0xFE` は「関節 0 だけオフ」です。机上の対象が ch0 なら、オフにするのは 1〜7 と足です。

## 右足スレーブ

別の ATOMS3 Lite が I2C スレーブになり、DF9-40 四隅をミリボルトで返します。WhoAmI は `'F'`（`0x46`）。ESP32 スレーブは Repeated START で欠けることがあるので、レジスタポインタは STOP 付きで書いてから読みます。
