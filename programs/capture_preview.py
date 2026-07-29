"""USB / HDMI キャプチャデバイスの映像プレビュー（Windows 向け簡易テスト）。

依存:
  pip install opencv-python

実行例:
  # 接続デバイスを列挙
  python programs/capture_preview.py --list

  # デバイス 0 をプレビュー（既定）
  python programs/capture_preview.py

  # デバイス番号・解像度を指定
  python programs/capture_preview.py --device 1 --width 1280 --height 720

操作:
  q … 終了
  s … 現在フレームを capture_frame.png に保存
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2


def list_devices(max_index: int = 10) -> None:
  """インデックス 0..max_index-1 を試し、開けるデバイスを表示する。"""
  print(f"Scanning capture devices (0..{max_index - 1}) via DirectShow...")
  found = 0
  for i in range(max_index):
    # Windows では CAP_DSHOW の方が CAP_ANY より失敗しにくいことが多い
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
      w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
      h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
      fps = cap.get(cv2.CAP_PROP_FPS)
      print(f"  [{i}] OK  {w}x{h}  fps≈{fps:.1f}")
      found += 1
      cap.release()
    else:
      print(f"  [{i}] —")
  if found == 0:
    print(
      "No openable devices. Check cable/driver and that another app is not using the device."
    )
  else:
    print(f"Found {found} device(s).")


def open_capture(
  device: int,
  width: int | None,
  height: int | None,
  fps: float | None,
) -> cv2.VideoCapture:
  """指定デバイスを開き、可能なら解像度・FPS を要求する。"""
  cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
  if not cap.isOpened():
    raise RuntimeError(
      f"Failed to open device {device} (CAP_DSHOW). Try --list or another --device."
    )

  if width is not None:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
  if height is not None:
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
  if fps is not None:
    cap.set(cv2.CAP_PROP_FPS, fps)

  # ドライバが無視することもあるので、実際に効いた値をログする
  actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
  actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
  actual_fps = cap.get(cv2.CAP_PROP_FPS)
  print(f"Opened device {device}: {actual_w}x{actual_h} fps≈{actual_fps:.1f}")
  return cap


def preview(
  device: int,
  width: int | None,
  height: int | None,
  fps: float | None,
) -> None:
  """ライブプレビュー。q で終了、s でスナップショット。"""
  cap = open_capture(device, width, height, fps)
  window = f"capture preview (device {device}) — q:quit s:save"
  cv2.namedWindow(window, cv2.WINDOW_NORMAL)

  # 簡易FPS計測
  t0 = time.perf_counter()
  frames = 0
  last_report = t0

  try:
    while True:
      ok, frame = cap.read()
      if not ok or frame is None:
        print("Frame grab failed (signal lost?). Retrying...")
        time.sleep(0.05)
        continue

      frames += 1
      now = time.perf_counter()
      if now - last_report >= 1.0:
        measured = frames / (now - t0)
        # ウィンドウタイトルに実測FPSを載せると確認しやすい
        cv2.setWindowTitle(window, f"{window} | measured {measured:.1f} fps")
        last_report = now

      cv2.imshow(window, frame)
      key = cv2.waitKey(1) & 0xFF
      if key == ord("q"):
        break
      if key == ord("s"):
        path = "capture_frame.png"
        cv2.imwrite(path, frame)
        print(f"Saved {path}")
  finally:
    cap.release()
    cv2.destroyAllWindows()


def main() -> int:
  parser = argparse.ArgumentParser(
    description="Capture device preview test (Windows / OpenCV)."
  )
  parser.add_argument(
    "--list",
    action="store_true",
    help="List openable capture devices and exit.",
  )
  parser.add_argument(
    "--device",
    type=int,
    default=0,
    help="Capture device index (default: 0).",
  )
  parser.add_argument("--width", type=int, default=None, help="Request frame width.")
  parser.add_argument("--height", type=int, default=None, help="Request frame height.")
  parser.add_argument(
    "--fps",
    type=float,
    default=None,
    help="Request FPS (driver may ignore).",
  )
  parser.add_argument(
    "--scan-max",
    type=int,
    default=10,
    help="Max index for --list (default: 10).",
  )
  args = parser.parse_args()

  if args.list:
    list_devices(args.scan_max)
    return 0

  try:
    preview(args.device, args.width, args.height, args.fps)
  except RuntimeError as e:
    print(e, file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
