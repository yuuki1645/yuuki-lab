# ATOM Field Manual

このディレクトリは **机上の `rt-usb`（USB ver 14）が自分で運ぶ現場手帳**です。ファームと同じリポジトリに置き、Hub がビルド時に文字列として取り込みます。ランタイムで GitHub を引きません。

機体の制御はここではありません。腰の CoreS3 と両脚の ATOM S3R（`can-leg`）は [docs/robot_control.md](../../../docs/robot_control.md) です。この手帳の「机上と機体の違いは Lab / Robot」は、`rt-usb` の中だけの話です。

読む場所:

- Robotics Hub の **実機テレメトリ（M5）**（`/m5-telemetry` →「ATOM 手帳」）
- 同じ手帳が **ATOM 机上ラボ**（`/atom-bench`）にも載っています
- 直リンク例: `/atom-bench?tab=profile#manual/nvs`

いまのプロトコルは、この手帳の対象である USB **ver 14**（`rt-usb`）です。章番号とファイルを揃えています。機体の USB は CoreS3 の ver 15 で、別の文書です。

| ファイル | 章 | 内容 |
|---|---|---|
| `00-map.md` | 地図 | Hub / Python / CDC / I2C の一列 |
| `01-boards.md` | 基板 | Lite と S3R、フラッシュ区画、NVS キー |
| `02-firmware.md` | ファーム | 双コア、Lab/Robot、有効マスク、ver 表 |
| `03-usb.md` | USB | バイナリフレームとメッセージ番号 |
| `04-tools.md` | 道具 | lab_debug、Hub の 2 画面、イベント 5000 |
| `05-nvs.md` | 有効と NVS | 経路を残して切る。空欄の意味 |
| `06-layers.md` | 層 | CDC、キャッシュ、なぜダンプが落ちるか |
| `07-notes.md` | 現場メモ | ログの読み方と、次に直すと効くこと |

章を足すときは `*.md` を追加し、`robotics-hub/src/features/m5-telemetry/field-manual/chapters.ts` に 1 件足してください。Markdown は見出し・表・リスト・コード・太字・インラインコードだけが画面に出ます（薄いパーサです）。
