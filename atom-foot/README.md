# atom-foot

脚の ATOMS3 Lite を I2C マスター、足裏の ATOMS3 Lite を I2C スレーブにして、
足裏四隅の DF9-40@2kg 圧力を PC の Python GUI で見るプロジェクトです。

`atom-rt` の GUI / USB フレームを参考に実装しています。由来は別リポジトリ `atoms3-on-foot` です。

---

## 構成

```
PC
 └ USB-C
    └ ATOMS3 Lite（脚・I2C マスター）
         └ Grove（SDA=G2 / SCL=G1）
              └ Grove Hub
                   └ Grove
                        └ ATOMS3 Lite（足裏・I2C スレーブ）
                             └ DF9-40 × 4 隅
```

| 役割 | ボード | PlatformIO 環境 | 給電 |
|------|--------|-----------------|------|
| マスター | 脚の ATOMS3 Lite | `i2c_master` | PC の USB-C |
| スレーブ | 足裏の ATOMS3 Lite | `i2c_slave` | Grove Hub の 5V（マスター経由） |

両方を USB 給電したままだと Grove の 5V 同士が Hub で短絡します。長時間の二重給電は避けてください。スレーブは書き込み後に USB を外し、Grove だけで動かします。

---

## 配線（正しい回路）

質問の分圧は **正しい** です。

```
3.3V -- DF9-40(Rs) --+-- ADCピン
                      |
                    10kΩ
                      |
                     GND
```

- 力が増えると DF9-40 の抵抗が下がる → ADC 電圧が上がる
- 無負荷では Rs が数 MΩ 以上なので、ADC はほぼ 0 V
- 換算: `Vout = 3.3 * 10k / (Rs + 10k)`、`Rs = 10k * (3.3 / Vout - 1)`

**Grove の 5V（赤線）でセンサーを励磁しないでください。**  
2 kg 付近では分圧が約 4.1 V になり、ESP32-S3 の ADC 入力（最大約 3.3 V）を超えます。

センサー電源は **ATOMS3 Lite 表面の 3V3 ピンソケット**（Grove PORT.CUSTOM ではない）から取ります。G38 などの GPIO は使いません。

### 1. PC ↔ マスター ↔ スレーブ（Grove）

```
PC USB-C ── 脚 ATOMS3 Lite USB-C

脚 ATOMS3 Lite Grove (PORT.CUSTOM)
    黄 G2 SDA ── Grove Hub ── 黄 G2 SDA  足 ATOMS3 Lite Grove
    白 G1 SCL ── Grove Hub ── 白 G1 SCL
    赤 5V     ── Grove Hub ── 赤 5V      （スレーブ給電）
    黒 GND    ── Grove Hub ── 黒 GND
```

- I2C 100 kHz、スレーブアドレス `0x28`
- ATOMS3 Lite の Grove には基板上の I2C プルアップがありません。短いケーブルなら内部プルアップで動くことが多いです。不通なら SDA/SCL を 3.3V へ 4.7 kΩ でプルアップしてください

### 2. 足裏スレーブ ↔ DF9-40 × 4

足裏を **上面・つま先が上** に置いたときの四隅です（robotics-hub と同じ並び）。

| 位置 | ピン | 内容 |
|------|------|------|
| 左上（つま先左） | G5 | ADC1 |
| 右上（つま先右） | G6 | ADC1 |
| 右下（かかと右） | G7 | ADC1 |
| 左下（かかと左） | G8 | ADC1 |
| センサー 3.3V（共通） | **表面 3V3** | Grove ではないピンソケット |
| GND（共通） | GND | 底面ヘッダの GND |

1 隅あたり:

```
表面 3V3 ── DF9-40 の一方 ──┬── その隅の ADC (G5/G6/G7/G8)
                           │
                        10kΩ（分圧）
                           │
                          GND
```

DF9-40 は抵抗なので極性はありません。4 本の 3.3V 側は表面 3V3 ソケットでまとめて、GND 側も共通で構いません。10kΩ は **隅ごとに 1 本**、ADC ピンと GND の間です。

ADC 用 GPIO の並びは個体のシルクを見てください。G38 / G39 は ADC 非対応です。使わないでください。

```
        つま先
   G5 左上        G6 右上

        [ATOMS3 Lite]

   G8 左下        G7 右下
        かかと
```

---

## 書き込み

必要: PlatformIO Core（`pio`）、Python 3.10 以降。

USB CDC です。**GUI / `usb_log.py` / シリアルモニタを開いたままでは書けません。**

1. スレーブを USB-C で PC に接続する
2. リセットを約 2 秒押し、**緑 LED が点いたら離す**
3. スレーブへ書き込む

```text
pio run -e i2c_slave -t upload
```

4. スレーブの USB を外し、Grove Hub 経由でマスターにつなぐ
5. マスターを USB-C で接続し、同じくダウンロードモードにして書き込む

```text
pio run -e i2c_master -t upload
```

COM が複数あるとき:

```text
pio run -e i2c_slave  -t upload --upload-port COMx
pio run -e i2c_master -t upload --upload-port COMy
```

既定環境は `i2c_master` です。

---

## Python GUI

```text
pip install -r tools/requirements.txt
python tools/foot_pressure_gui.py
```

- COM を選んで接続（VID `303A` の ATOMS3 が先頭）
- 足裏フレーム四隅がヒート表示される（低=シアン、高=赤）
- 中央が合計 kg、白い点が圧力中心の概算
- 右は力と分圧電圧の時系列
- Identify: マスターと足側の LED が虹色
- Ping: HELLO を再送させる

通信は **固定長バイナリフレーム**（マジック `AA 55` + CRC-16）です。
`pio device monitor` はバイナリを文字化けさせるので、確認は GUI か:

```text
python tools/usb_log.py
```

LED:

| ボード | 色 | 意味 |
|--------|----|------|
| マスター | 緑 | スレーブ応答あり |
| マスター | 赤点滅 | スレーブ未応答 |
| マスター | 虹色 | Identify / 正面ボタン |
| スレーブ | シアン〜赤 | 合計荷重の目安（Identify 中は虹色） |

---

## ディレクトリ

```
include/          共通（I2C レジスタ、USB フレーム、DF9 換算、ピン）
src/master/       脚マスター（I2C + USB）
src/slave/        足スレーブ（ADC + I2C スレーブ）
tools/            Python GUI / プロトコル / 力換算
```

I2C レジスタ（スレーブ `0x28`）:

| 番地 | 内容 |
|------|------|
| `0x00` | WHO_AM_I (`0x46` = 'F') |
| `0x01` | プロトコル版 |
| `0x10`–`0x17` | 四隅ミリボルト uint16 LE（TL, TR, BR, BL） |
| `0x20`–`0x22` | スレーブ LED R/G/B |

力換算の正本は `tools/df9_force.py`（データシート 2 kg 列の log-log 補間）。USB ではミリボルトだけ送り、kg は PC で計算します。
