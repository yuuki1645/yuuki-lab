# CAD テスト（build123d / Open CASCADE）

いまの実機（カゴと両脚）を、URDF と同じ箱で STEP にする実験です。穴、ホーン、金具はまだ作りません。最初の合格は、サーボが STEP から同じ外形で戻ることです。

寸法は `robot_description/yuuki_biped.yaml` だけが正本です。このディレクトリの Python はその yaml を読み、`generate_urdf.py` と同じ箱の置き方を使います。数値はここに写していません。

座標系は URDF と同じです。x が前、y が左、z が上。原点は股ロール軸の高さで、左右の中央です。カゴの箱はその上に浮いています。全関節 0 が、脚をまっすぐ下へ伸ばした直立です。

## 実行

リポジトリルートで:

```powershell
python -m pip install -r cad/requirements.txt
python cad/export_step.py
```

`build123d` が Open CASCADE の Python バインディング（OCP）を入れます。立体は build123d で作り、読み戻しの寸法検査だけ `cad/check_step.py` が OCP を直接呼びます。

生成物は `cad/out/` です。

| ファイル | 中身 |
| --- | --- |
| `servo_rds51150.step` | ピッチ向きのサーボ1個。軸は原点 |
| `left_leg.step` | 左脚。位置は全身と同じ世界座標 |
| `yuuki_biped.step` | カゴと両脚 |

Python の中の数値はメートルです。STEP に書くとき build123d がミリメートルに直します。サーボの半幅 15 は 15 mm です。読み戻しは Open CASCADE がミリメートルで返すので、検査もそれに合わせています。

股間隔、隙間 4 mm、足首から足裏まで、足板の前後位置は、yaml に書いてある仮値のままです。金具を測ったら yaml を変えて、このスクリプトをやり直してください。

## 等身大の全身（既存設計とは別）

`cad/humanoid/` は、カゴと脚の実機を使わない新規の概念モデルです。直立で足裏から頭頂まで 170 cm。寸法の正本は `humanoid/params.py` です。

```powershell
python cad/export_humanoid.py
```

生成物は `cad/out/yuuki_humanoid.step` です。頭、胴、両腕、両脚を、円柱の肢とピッチ関節のハウジングで置いています。ボルト、軸受、内部フレームはまだありません。
