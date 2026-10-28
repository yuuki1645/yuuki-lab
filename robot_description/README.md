# yuuki_biped の URDF

現状の実機（カゴ＋両脚。バランス棒は無い）を、箱の組み合わせで表した URDF です。Isaac Lab 専用ではなく、URDF を読めるシミュレータ向けの共通の記述です。`isaac-lab` 以下の古いモデルとは別物です。

数値の編集は `yuuki_biped.yaml` だけにします。URDF は生成物です。

## 作り直す

プロジェクトルートで:

```powershell
python robot_description/generate_urdf.py
```

`yuuki_biped.yaml` を読んで、同じディレクトリの `yuuki_biped.urdf` を上書きします。慣性テンソルは箱の寸法と質量から計算します。別のパスにするときは `--config` と `--output` を付けます。

## 座標系

原点はカゴ底面の中央です。x が前、y が左、z が上。ベースは地面に固定していません。全関節 0 が、脚をまっすぐ下へ伸ばした直立です。

ピッチ軸は +Y です。右手系なので、正の角度は脚を後ろへ曲げます。膝の 0 は伸び、正は屈曲です。

左脚のロール軸は +X です。正の角度は脚を左（外側）へ開きます。右脚は `right_roll_axis_sign: -1` で軸が -X になり、正の角度が右（外側）へ開きます。実機のサーボ符号と違う場合は、この符号か関節範囲を入れ替えてください。符号を反転すると、範囲の上下も物理的に同じ向きのままになるようスクリプト側で入れ替えます。

## リンクと関節

片脚は上から次の5関節です。左右で名前の `left` / `right` が変わります。


| 関節            | 親 → 子            | 中身                   |
| ------------- | ---------------- | -------------------- |
| `hip_roll`    | `basket` → `hip` | 股ロールのサーボ             |
| `hip_pitch`   | `hip` → `thigh`  | 股ピッチのサーボ、腿の板2枚、バッテリー |
| `knee_pitch`  | `thigh` → `shin` | 膝サーボ、脛の板2枚、バッテリー     |
| `ankle_pitch` | `shin` → `ankle` | 足首ピッチのサーボ            |
| `ankle_roll`  | `ankle` → `foot` | 足首ロールのサーボ、足裏の板       |


`imu_link` はカゴに固定した参照フレームです。`left_sole` と `right_sole` は足裏下面の中心です。どちらも質量はほぼゼロで、接触形状は足板の方にあります。

## 図面どおりの値と、仮の値

図面と `docs/robot_spec.md` から採っているもの:

- カゴ 18 × 28 × 14.5 cm（前後 × 左右 × 高さ）
- サーボ 30 × 48 × 65 mm（前後 × 左右 × 脚方向）、180 g、トルク 14.7 N·m
- 軸はサーボ上端から 13 mm
- アルミ板 4 cm × 3 mm × 20 cm、63 g。腿・脛とも両側に1枚
- リポ 24 mm × 4 cm × 13 cm、302 g。脛にも1本（`battery.on_shin`）
- 足裏 30 × 17 × 0.2 cm、271 g

図面に無いので仮置きしているもの（yaml にコメントあり）:


| キー                                   | 初期値                                                    | 意味                        |
| ------------------------------------ | ------------------------------------------------------ | ------------------------- |
| `placement.hip_x_m`                  | 0                                                      | 股軸はカゴの前後中央                |
| `placement.hip_y_m`                  | 0.09                                                   | 左右の股軸は中心から 9 cm（間隔 18 cm） |
| `basket.mass_kg`                     | 0.6                                                    | カゴと基板のまとめ                 |
| `placement.segment_axis_distance_m`  | null → 0.226                                           | 13 mm ＋ 板 200 mm ＋ 13 mm  |
| `placement.stacked_servo_distance_m` | null → 0.065                                           | 板を挟まないサーボの軸間。箱の下端は隙間分短くする |
| `placement.clearance_m`              | 0.004                                                  | 未計測。箱どうしをこの隙間だけ離す         |
| `foot.ankle_to_sole_m`               | 0.058                                                  | 足首ロール軸から足裏まで。サーボが板を貫かない |
| `foot.center_x_m`                    | 0.05                                                   | 足板の中心は軸より 5 cm 前          |
| `plate.center_y_m`                   | 0.0295                                                 | サーボ側面から 4 mm 空けた側板         |
| `joints_deg`                         | 股ロール ±45°、股ピッチ −45〜+90°、膝 0〜120°、足首ピッチ ±45°、足首ロール ±30° | 機械ストッパは未計測                |
| `actuator.velocity_limit_rad_s`      | 8                                                      | 無負荷速度は未計測                 |
| `imu.xyz_m`                          | `[0, 0, -0.02]`                                        | カゴ底のすぐ下。IMU かどうかは未確認      |


`segment_axis_distance_m` と `stacked_servo_distance_m` を空（`null`）のままにすると、サーボと板の寸法から計算します。メジャーで軸間を測ったら、そのメートル値を直接書いてください。計算式より書いた値を優先します。

サーボの箱は「軸から下へ胴体が伸びる」置き方です。関節の位置は式のままです。`clearance_m` の分だけ、股と足首のサーボは下端を短くし、側板はサーボの側面と次のサーボから離し、電池は側板のあいだのダンボールとして上下のサーボに届かない位置に置きます。足裏は、足サーボの下端より隙間と板厚の分だけ下です。隙間は未計測の 4 mm なので、金具を測ったら `clearance_m` と `ankle_to_sole_m` を実測に替えて作り直してください。

## 初期値での目安

生成時にスクリプトが印字します。初期値ではおおよそ次のとおりです。

- 総質量 約 4.65 kg（カゴ 0.6 kg は仮定）
- 原点（股ロール軸の高さ）から足裏まで 0.640 m
- 足裏からカゴ天面まで 0.802 m。カゴの箱は股サーボの上端より 4 mm 上から始まる

カゴの重さを量ったら `basket.mass_kg` を差し替え、もう一度生成してください。総質量が実機の秤の値に近づいているかの確認に使えます。

## Hub から関節を動かす

実機の日とシミュの日は分けます。両方は同時に起動しません。

実機の日は、今までどおり Hub だけです。Isaac は起動しません。

```powershell
cd Z:\Projects\yuuki-lab\robotics-hub
npm run dev:m5
```

ブラウザは **実機テレメトリ（M5）** の「脚」タブです。左列は実機に脚が無いので暗いまま、右列が今までどおり動きます。

シミュの日は、`isaac-sim.bat` と `npm run dev:m5` は使いません。プロセスは3つです。

```powershell
cd Z:\Projects\yuuki-lab\robotics-hub
npm run dev

python Z:\Projects\yuuki-lab\robot_description\isaac_hub_bridge.py

C:\isaacsim\python.bat Z:\Projects\yuuki-lab\robot_description\isaac_hub_play.py
```

橋は Hub 用の Python（`flask-socketio` が入っているもの）で起動します。`C:\isaacsim` にはパッケージを入れません。再生スクリプトが Isaac Sim の窓を開きます。画面は同じ「脚」タブで、`:8794` が無いので `:8795` の橋へつながります。135° が直立です。電圧・電流は暗いまま残ります。PWM ON のあと、バーのつまみを掴むと関節が追います。

足裏は、アルミ板と床の接触を四隅の kg（各 2 kg で頭打ち）に分配して、左右とも同じ欄に出します。実機は右足だけなので、実機の日は左足裏が「未検出」のままです。カゴは地面に固定したままなので、画面に出る荷重はロボット全体の体重ではなく、脚が床を押した力です。足首を傾けると、下げた隅が大きくなります。

## Isaac Lab や sim-to-real で使うとき

歩行の学習タスクは `YuukiLab-BipedWalk-v0` です。アセットは `isaac-lab` 拡張の `assets/robots/yuuki_legs` から、この URDF をカゴ固定なしで読みます。変換結果は `.usd_float` です。Hub 再生の `.usd_cache` はカゴ固定なので、学習には使いません。

conda の `env_isaaclab` は使いません。Isaac Lab 3 から起動します。

```powershell
cd Z:\Projects\IsaacLab-3
isaaclab.bat -p Z:\Projects\yuuki-lab\robot_description\stand_one.py --viz kit
```

窓が開き、脚を伸ばした姿勢（全関節 0）を数秒保ちます。閉じるまでシミュレーションは続きます。コンソールに、カゴ底の高さ・カゴの上方向・左右の足裏の高さが 1 秒ごとに出ます。足裏が床に乗った直立なら、カゴ底は約 0.640 m、足裏は 0 m 付近です。

窓なしで数値だけ出すときは `--viz kit` を外します。

トルク上限と速度上限は URDF の `limit` に入っています。位置制御の PD ゲインは URDF に無く、この確認では再生スクリプトと同じ仮の値（剛性 80、減衰 2）を使っています。

実機と揃えるときに効くのは、左右の股の間隔、足板の前後位置、足首から足裏までの距離、直立が本当に 0 か、ロールの符号、です。

## ゲームパッドで踵を動かす

この README の `isaac_hub_play.py` は、画面のバーで関節を追わせる起動です。スティックで左右の踵を動かす起動（`env_isaaclab` と `manual_heel_teleop.py`、実機は `link/host/heel_gamepad.py`）は [docs/heel_teleop.md](../docs/heel_teleop.md) です。実機の `:8794` と、この橋の `:8795` は同時に画面へ出しません。