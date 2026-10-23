# link

ATOM と CoreS3 が共有する USB 契約と、サブ PC がケーブルを握る入口です。

| 場所 | 役割 |
|---|---|
| `include/usb_frame.hpp` | フレーム、CRC、メッセージ番号 |
| `py/rt_usb_proto.py` | 上と同じ並びの Python |
| `host/lab_debug.py` | COM を開くプロセス。中継は Socket.IO :8794 |

テレメトリの中身は版で違います。ver 14 は片脚 8 軸、ver 15 は CoreS3 の 10 軸と両足です。番号を足すときは `usb_frame.hpp` と `rt_usb_proto.py` を同じ変更にします。
