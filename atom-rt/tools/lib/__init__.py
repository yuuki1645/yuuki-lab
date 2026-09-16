"""
atom-rt の Python ライブラリ（直接起動しない）。

起動物は親ディレクトリの 3 本だけ:
  tools/lab_debug.py     本線 GUI（複数 ATOM・Hub 中継）
  tools/rt_monitor.py    従来の 1 台グラフ
  tools/rt_usb_log.py    ターミナルの送受信ログ

このパッケージ（tools/lib/）は上から import される部品:
  rt_usb_proto.py      USB バイナリフレーム（ファーム usb_proto.hpp と揃える）
  cal_map_io.py        校正マップ JSON（as5600-servo-map-v1）
  m5_hub_bridge.py     Hub / iPad 向け Socket.IO と本記録 REST（:8794）
  m5_record_store.py   本記録のディスク保存
  cop_ankle_ctrl.py    かかとピッチ COP の PC 閉ループ
  df9_force.py         足裏 DF9-40 の電圧→力換算

`python tools/lab_debug.py` では sys.path に tools/ が入るので
`import lib.rt_usb_proto` で読む。
"""
