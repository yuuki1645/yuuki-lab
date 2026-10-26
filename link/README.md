# link

ATOM と CoreS3 が共有する USB 契約と、サブ PC がケーブルを握る入口です。

| 場所 | 役割 |
|---|---|
| `include/usb_frame.hpp` | フレーム、CRC、メッセージ番号 |
| `py/rt_usb_proto.py` | 上と同じ並びの Python |
| `host/lab_debug.py` | COM を開くプロセス。中継は Socket.IO :8794 |

テレメトリの中身は版で違います。ver 14 は片脚 8 軸、ver 15 は CoreS3 の 10 軸と両足です。番号を足すときは `usb_frame.hpp` と `rt_usb_proto.py` を同じ変更にします。

## 実験記録

CoreS3 の USB ver 15 HELLO から切断まで、`lab_debug.py` がセンサー・指令・イベントを自動で残します。実験名の入力はありません。ver 14 の片脚接続では記録しません。

保存先はリポジトリの外です。`storage.example.yaml` を次のファイルへコピーし、パスだけ書き換えます。

```text
C:\Users\<ユーザー名>\.yuuki-lab\storage.yaml
```

`data_root` は実験中に書くローカル SSD、`archive_root` は閉じたファイルを置く NAS 上の親フォルダです。NAS のホスト名やパスワードは書きません。フォルダは `年/月/日/時分秒/` です。各 take には欄の説明 `schema.md` が入ります。正本は [schema/core_take_v1.md](schema/core_take_v1.md) です。
