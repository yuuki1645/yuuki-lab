# link

ATOM と CoreS3 が共有する USB 契約と、サブ PC がケーブルを握る入口です。機体の全体は [docs/robot_control.md](../docs/robot_control.md) です。

| 場所 | 役割 |
|---|---|
| `include/usb_frame.hpp` | フレーム、CRC、メッセージ番号 |
| `py/rt_usb_proto.py` | 上と同じ並びの Python |
| `host/lab_debug.py` | COM を開くプロセス。中継は Socket.IO :8794 |
| `host/usb_hub_watch.ps1` | サインイン後に残る監視。VID `303A` で rt-usb が見えたら Hub を起動する |
| `host/usb_hub_watch.ico` | 時計の横に出す絵。元の画像は隣の `usb_hub_watch.png` |
| `host/install_usb_watch.cmd` | 監視をスタートアップへ登録する。外すのは `uninstall_usb_watch.cmd` |

テレメトリの中身は版で違います。ver 14 は片脚 8 軸、ver 15 は CoreS3 の 10 軸と両足です。番号を足すときは `usb_frame.hpp` と `rt_usb_proto.py` を同じ変更にします。

## USB を挿したら Hub を開く

常駐するのは `host/usb_hub_watch.ps1` だけです。時計の横の絵は `host/usb_hub_watch.ico` です。差し替えたら監視を終了して、もう一度 `just usb-watch-on` です。右クリックでログを開くか、監視だけ終了できます。`^` の中に入っているときは、そこからドラッグして外に出せます。`robotics-hub` と `lab_debug.py` は、ボードが rt-usb のフレームを出しているときだけ `npm run dev:m5` で起動します。ケーブルは 1 本です。机の rt-usb（ver 14）ならブラウザで `http://127.0.0.1:5173/atom-bench`、腰の CoreS3（ver 15）なら `http://127.0.0.1:5173/m5-telemetry` を開きます。長さで版が分からないときは実機テレメトリです。ケーブルを抜いても Hub は止めません。

登録は今サインインしているユーザーだけです。どちらか一方で足ります。

```text
just usb-watch-on
link\host\install_usb_watch.cmd
```

外すときは `just usb-watch-off` または `link\host\uninstall_usb_watch.cmd` です。失敗したときの記録は `%LOCALAPPDATA%\yuuki-lab\usb_hub_watch.log` です。

ダウンロードモードはフレームを出さないので、監視はポートをすぐ閉じます。`pio` や `esptool` が動いているあいだは開きません。すでに Hub が COM を握っているときは、書く前にその窓を閉じてください。

## 実験記録

CoreS3 の USB ver 15 HELLO から切断まで、`lab_debug.py` がセンサー・指令・イベントを自動で残します。実験名の入力はありません。ver 14 の片脚接続では記録しません。

保存先はリポジトリの外です。`storage.example.yaml` を次のファイルへコピーし、パスだけ書き換えます。

```text
C:\Users\<ユーザー名>\.yuuki-lab\storage.yaml
```

`data_root` は実験中に書くローカル SSD、`archive_root` は閉じたファイルを置く NAS 上の親フォルダです。NAS のホスト名やパスワードは書きません。フォルダは `年/月/日/連番_時分秒/` です。連番はその日の何本目かで、消しても詰めません。各 take には欄の説明 `schema.md` が入ります。正本は [schema/core_take_v1.md](schema/core_take_v1.md) です。
