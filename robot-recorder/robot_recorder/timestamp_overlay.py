"""映像フレームへの JST 時刻焼き込み。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import cv2

_JST = ZoneInfo("Asia/Tokyo")


def format_jst_now_ms() -> str:
  """例: 2026-07-30 20:15:03.123"""
  now = datetime.now(_JST)
  return now.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(now.microsecond / 1000):03d}"


def burn_jst_timestamp(frame):  # noqa: ANN001 — numpy BGR
  """左上に半透明帯 + 白文字で時刻を描く（破壊的に frame を変更）。"""
  text = format_jst_now_ms()
  font = cv2.FONT_HERSHEY_SIMPLEX
  scale = 0.7
  thickness = 2
  (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
  pad = 8
  x0, y0 = 8, 8
  x1, y1 = x0 + tw + pad * 2, y0 + th + baseline + pad * 2
  overlay = frame.copy()
  cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 0, 0), -1)
  cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
  cv2.putText(
    frame,
    text,
    (x0 + pad, y0 + pad + th),
    font,
    scale,
    (255, 255, 255),
    thickness,
    cv2.LINE_AA,
  )
  return frame
