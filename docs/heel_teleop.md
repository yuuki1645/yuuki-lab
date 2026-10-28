# ゲームパッドによる踵操作

強化学習の歩行とは別の操作です。方策は使いません。腰（カゴ底の中心）を原点にして、左右の踵を動かします。機体は [robot_description](../robot_description/README.md) の両脚です。バランス棒のある古いモデルは使いません。

シミュレータと実機で、スティックの向きと積算は同じです。違うのは、角度の送り先と、実機だけにある床側の止めです。

135° が直立（関節 0 rad）です。画面の度は、この中立からのずれです。

## 操作

パッドは、そのスクリプトを動かしている PC に挿します。Logicool のパッドは Windows では Xbox 360 Controller として見えます。読み取りは XInput です。

腰が原点です。直立では +Z が天井です。スティックは、腰の +Z 方向から見た XY です。ロボットが倒れても、指令は部屋ではなく、その瞬間の腰の軸に残ります。

| 入力 | 動き |
|---|---|
| 左スティック | 左踵。奥が腰の +X（前）、右がロボットの右（腰の −Y） |
| 右スティック | 右踵。向きは左と同じ |
| L / R（バンパー） | 押しているあいだ、その踵を腰の天井側（+Z）へ |
| ZL / ZR（トリガー） | 引いているあいだ、その踵を腰の床側（−Z）へ |
| スタート | 押しているあいだ、全関節 135° のときの両踵へ約 0.06 m/s で戻る。離すと止まる |

スティックを中立に戻しても、そこまでの踵は戻りません。次に倒すと、記憶している位置から続きます。全関節 135° の位置へ戻すのはスタートだけです。届かない一歩は目標に溜めません。

倒し切りの速さは、前後左右 0.30 m/s、床側（トリガー）0.20 m/s です。不感帯のあとで倒し量を二乗するので、半分の倒しはおおよそ 4 分の 1 の速さです。スティックの不感帯は 0.15、トリガーは 0.08 です。バンパーは押しているかどうかだけなので、天井側は上下最高速の約 1/3（約 0.067 m/s）です。

足裏は、足首の可動域に収まるあいだ腰の XY と平行に保ちます。足首が端に当たったら、踵の位置を優先して足裏は傾きます。

脚が伸び切って、その高さのまま水平に動けないときは、指令した XY を残して、届くいちばん近い高さへ Z だけずらします。

## 同時に起動しないもの

実機の日とシミュの日は分けます。

| 動かしているもの | 止めておくもの |
|---|---|
| シミュの手動操作 | `npm run dev:m5` と `lab_debug.py`（:8794）。Isaac の窓は 1 つ |
| 実機の手動操作 | Isaac の窓と `isaac_hub_bridge.py` |
| 歩行の学習・再生 | 手動操作の Isaac。同じ Kit を二重には開かない |

画面は先に :8794 を試し、無ければ :8795 へつなぎます。`lab_debug.py` が残っていると、橋を上げても画面は実機のままです。

Isaac の窓を閉じたあとプロセスが残ることがあります。残っているあいだに次の Isaac を開かないでください。タスクマネージャーでそのプロセスを終えてから、もう一度起動します。

## シミュレータ

Python は conda の `env_isaaclab` です。`C:\isaacsim\python.bat` や `Z:\Projects\IsaacLab-3` からは起動しません。拡張は一度入れてあれば足ります。

```powershell
cd Z:\Projects\yuuki-lab\isaac-lab
python -m pip install -e source/yuuki_isaac_lab
```

この PC では Vulkan のまま窓を開くと落ちます。`--kit_args` の値は、ハイフンで始まる 1 つの引数として渡します。

```powershell
conda activate env_isaaclab
cd Z:\Projects\yuuki-lab\isaac-lab
python .\scripts\manual_heel_teleop.py "--kit_args=--/app/vulkan=false"
```

PowerShell が `>>` で止まったときは、`--/app/vulkan=false` が別の引数になっています。上の 1 行のまま再実行してください。

スクリプトはパッドによるカメラ操作を切ります。スティックは視点ではなく踵に使います。

窓の中の印:

| 球 | 意味 |
|---|---|
| 緑 | 左踵の目標 |
| 橙 | 右踵の目標。照明で黄色に見えることがある |
| 黄（カゴの下） | `imu_link`。目標ではない |
| 赤（足裏） | モデルに付いている印。目標ではない |

コンソールに左右の目標が約 2 秒ごとに出ます。橋が無いときは、一度だけ「画面には出しません」と出て、操作はそのまま続きます。あとから橋を上げると、こちらからつなぎ直します。

窓なしはパッドを読みません。モデルの確認用です。

```powershell
python .\scripts\manual_heel_teleop.py --headless --steps 8
```

### 画面に出す

別の端末を 2 つ使います。`npm run dev:m5` は使いません。USB 監視が Hub を上げているときは、その窓を閉じてからにします。

```powershell
conda activate env_isaaclab
cd Z:\Projects\yuuki-lab
python .\robot_description\isaac_hub_bridge.py
```

```powershell
cd Z:\Projects\yuuki-lab\robotics-hub
npm run dev
```

ブラウザは [http://127.0.0.1:5173/m5-telemetry](http://127.0.0.1:5173/m5-telemetry) の「脚」タブです。

| 欄 | 中身 |
|---|---|
| 指令 | 逆運動学の目標角 |
| 補正（シミュ） | シミュレータの今の関節角 |
| 足裏 | 床との接触を四隅の kg に分けた値。各隅 2 kg で頭打ち |

バーはドラッグできません。PWM のボタンは出ません。電圧と電流は空です。キャプションが「手動の踵操作です」なら、この経路です。「歩行再生です」は方策の再生で、別の操作です。

歩行再生と、バーで関節を追わせる `isaac_hub_play.py` の起動は [robot_description/README.md](../robot_description/README.md) です。

## 実機

サブ PC が CoreS3 の USB を握っている状態で、同じ PC にパッドを挿します。このスクリプトは COM を開かず、PWM も入れません。

先に実機テレメトリを上げます。

```powershell
cd Z:\Projects\yuuki-lab\robotics-hub
npm run dev:m5
```

ブラウザは [http://127.0.0.1:5173/m5-telemetry](http://127.0.0.1:5173/m5-telemetry) です。ブリッジがつながってから、次を実行します。

```powershell
conda activate env_isaaclab
cd Z:\Projects\yuuki-lab
python .\link\host\heel_gamepad.py
```

指令角が届くまで最大 10 秒待ち、その角度を最初の踵にします。補正角は使いません。欠測の軸は 135° です。PWM を入れる前にスティックを倒すと目標だけ先に進むので、入れる瞬間にその位置へ動きます。スタートは、今の指令ではなく、全関節が 135° のときの踵へ戻します。

動かしたい関節は、画面で PWM を入れてください。足裏の合計が 0.5 kg 以上のあいだは、その足の床側（腰の −Z）だけ止めます。上げる動きと、水平の動きと、足が浮いているときの下げは通ります。足裏が未検出のときは止めません。

角度は URDF の可動域と、ファームが受ける 40〜230° の内側です。画面の机上実験用 100〜170° は使いません。その範囲だと膝が約 35° しか曲がらず、シミュと同じように足を上げられません。膝の上限だけ、URDF の 120° より手前の 230°（中立 135° から +95°）で止まります。

Ctrl+C で送出が止まります。PWM が入っている脚は、指令が約 200 ms 途切れると脱力します。

パッドも USB も使わず、床止めと可動域だけ見るとき:

```powershell
python .\link\host\heel_gamepad.py --self-check
```

`heel_gamepad self-check: OK` と出れば、その確認は通っています。

## コード

| 場所 | 内容 |
|---|---|
| [isaac-lab/scripts/manual_heel_teleop.py](../isaac-lab/scripts/manual_heel_teleop.py) | シミュの窓とパッド |
| [manual_heel/leg_ik.py](../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/manual_heel/leg_ik.py) | 腰基準の逆運動学。実機もこのファイルを読む |
| [manual_heel/hub_telemetry.py](../isaac-lab/source/yuuki_isaac_lab/yuuki_isaac_lab/manual_heel/hub_telemetry.py) | シミュから 127.0.0.1:8796 へ出す |
| [robot_description/isaac_hub_bridge.py](../robot_description/isaac_hub_bridge.py) | 8796 を受け、画面の :8795 へ出す |
| [link/host/heel_gamepad.py](../link/host/heel_gamepad.py) | 実機。:8794 の `m5/cmd` へ関節角を出す |
