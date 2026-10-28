# 実機の制御

機体に載っている制御の基本です。寸法と重量は [robot_spec.md](robot_spec.md) です。机上で ATOM を USB 直結する手順は [現場手帳](../atom-rt/docs/field-manual/README.md)（`rt-usb`、USB ver 14）です。

## 役割

腰のカゴにある **CoreS3** が中央です。サブ PC とは USB-C でつなぎ、CoreS3 への給電と通信を兼ねます。両脚の **ATOM S3R** とは CAN でつなぎます。

各脚の ATOM S3R は、その脚のセンサを読んで CAN で腰へ送り、腰から届いた角度をサーボの PWM にします。次の角度は自分では計算しません。担当はセンサの入力と、サーボへの出力です。

角度を決める場所は腰の CoreS3 です。いまのファームは 20 Hz で計測を集め、指令を返します。歩行の計算はまだ入っていません。出している角度は、サブ PC から USB で届いた手動指令か、Robot モードの 135° 保持です。

CoreS3 の Core 1 が CAN と指令、Core 0 が USB です。Core 0 は集めたセンサをサブ PC へ送り、サブ PC からの指令も受けます。

サブ PC の `link/host/lab_debug.py` が USB を握り、Socket.IO（既定 **:8794**）に載せます。Hub を LAN に出すと、iPad などのブラウザが **実機テレメトリ（M5）**（`/m5-telemetry`）を開きます。Wi-Fi で流れているのは Hub の画面と Socket.IO で、センサの生パケットそのものではありません。

ラズパイの [robot-daemon](../robot-daemon/README.md) は、いまの関節指令の経路ではありません。Hub のモーションエディタ、ポーズエディタ、レッグサーボ調整、実機テレメトリ（IMU）は、まだこのデーモンの REST と Socket.IO（既定 **:5000**）を向いています。

## 基板

| 場所 | ボード | ファーム | 仕事 |
|---|---|---|---|
| 腰 | CoreS3 | [core-rt](../core-rt/)（USB ver 15） | 計測を集める。指令を返す。USB でサブ PC へ出す |
| 各脚 | ATOM S3R | [atom-rt](../atom-rt/) の `can-leg` | その脚のセンサと PWM |
| 各足裏 | ATOMS3 Lite | [atom-foot](../atom-foot/) の `i2c_slave` | DF9-40 四隅。I2C スレーブ `0x28` |
| サブ PC | Windows | [link](../link/) と [robotics-hub](../robotics-hub/) | USB を握る。画面を配る |

机上の単体確認は別ファームです。ATOM に `rt-usb`（USB ver 14）を焼いて USB でサブ PC へ直結します。足裏だけの確認は `atom-foot` の `i2c_master` です。

## 脚の配線

各 ATOM S3R の Grove（SDA=GPIO2、SCL=GPIO1、100 kHz）に PaHub が 2 台あります。

| PaHub | アドレス |
|---|---|
| 右もも | `0x70` |
| 左もも | `0x71` |
| 右すね | `0x72` |
| 左すね | `0x73` |

アドレスで右か左かを決めます。両方見える、またはどちらも無いときは、そのボードは PWM を出しません。

論理軸は 10 本です。0〜4 が右、5〜9 が左です。順は股ロール、股ピッチ、ひざ、かかとピッチ、かかとロールです。

片脚の 8Servos は 2 枚です。

- 股とひざは Grove 直下の 8Servos（`0x26`）。出力 0 が股ロール、1 が股ピッチ、2 がひざです。
- かかとはすねの PaHub の先の 8Servos（`0x25`）。出力 6 がかかとピッチ、7 がかかとロールです。右は `0x72` のチャンネル 0、左は `0x73` のチャンネル 5 です。

センサは次のとおりです。

- AS5600（`0x36`）が各軸の角度です。
- INA226（`0x41`）が各軸の電圧と電流です。
- 足裏スレーブ（`0x28`）は右が `0x72` のチャンネル 1、左が `0x73` のチャンネル 4 です。四隅の電圧を返します。

チャンネルの初期値は [core-rt/src/topology.hpp](../core-rt/src/topology.hpp) です。左右で番号が違います。経路の正本は CoreS3 の NVS で、CAN で脚へ配ります。CoreS3 は脚の I2C を開きません。

サーボは RDS51150 を想定しています。指令の範囲は 40〜230° です。

## CAN

500 kbit/s です。

- CoreS3 は PORT.C の Unit CAN です。送信は GPIO17、受信は GPIO18 です。Grove の 5V を出さないとトランシーバは動きません。この 5V は腰の Unit CAN 用で、脚やサーボの電源ではありません。
- ATOM S3R は Atomic CAN ベースです。送信は GPIO5、受信は GPIO6 です。

1 周期の計測は、片脚あたり 10 フレームに分かれます。CoreS3 が同じ連番で 1 サンプルに組み立てます。角度指令は片脚 2 フレームです。定義は [link/include/can_leg.hpp](../link/include/can_leg.hpp) です。

一度でも現れた脚が 200 ms 黙ると、CoreS3 はその周期の出力を切ります。脚は指令が 200 ms 途切れると、最後の角度のあと脱力します。

## 20 Hz

CoreS3 の制御タスクと、各脚のループは 50 ms（20 Hz）です。USB のテレメトリも 50 ms です。

この中でいま行っているのは、計測の組立、角度のアンラップ、校正マップの参照、欠測と過電流での出力カット、届いている指令角の送信です。政策の計算時間は 0 のままです。センサから次の角度を決める処理は、これからこの周期の中に入れます。

過電流の既定は、脚側で 8 A です。

## サブ PC とタブレット

```text
CoreS3  USB-C（ver 15）
    │
    ▼
サブ PC  link/host/lab_debug.py
    │ Socket.IO :8794
    ▼
Hub      :5173
    │
    ▼
ブラウザ  /m5-telemetry （iPad も PC もここ）
```

`robotics-hub` で `npm run dev:m5` を実行すると、Hub と `lab_debug.py` が同時に上がります。Vite は `0.0.0.0:5173` です。iPad はサブ PC の LAN の IP で `/m5-telemetry` を開きます。

ゲームパッドで左右の踵を動かす手順（シミュの Isaac 起動、画面への出し方、実機で PWM を入れる前の注意）は [heel_teleop.md](heel_teleop.md) です。実機側のスクリプトは `link/host/heel_gamepad.py` で、COM は `lab_debug.py` が握ったままです。

CoreS3 の HELLO から USB を抜くまで、センサと指令とイベントを自動で残します。保存先はユーザーの `storage.yaml` です。手順は [link/README.md](../link/README.md) です。画面から明示して残す本記録は `atom-rt/data/recordings` です。

## コードの場所

| 場所 | 内容 |
|---|---|
| [core-rt](../core-rt/) | 腰。`pio run -t upload` |
| [atom-rt](../atom-rt/) の `can-leg` | 脚。`pio run -e can-leg -t upload` |
| [atom-rt](../atom-rt/) の `rt-usb` | 机上。`pio run -e rt-usb -t upload` |
| [atom-foot](../atom-foot/) の `i2c_slave` | 足裏。書き込み後は USB を外し、Grove で給電する |
| [link](../link/) | USB のフレームと、COM を握る入口 |
| [robotics-hub](../robotics-hub/) | ブラウザ |

机上の疎通 `can-ping` は、この本線ではありません。
