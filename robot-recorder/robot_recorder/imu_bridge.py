"""Pi の robot-daemon から IMU を購読し、Recorder の latest / 記録へ流す。"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

_LOG = logging.getLogger(__name__)

if TYPE_CHECKING:
  from robot_recorder.app import RecorderApp


class ImuBridge:
  """Socket.IO クライアントで Pi → Recorder（表示・recording 中はファイル）。"""

  def __init__(self, app: RecorderApp, url: str, rate_hz: float = 10.0) -> None:
    self._app = app
    self.url = url.rstrip("/")
    self.rate_hz = rate_hz
    self._stop = threading.Event()
    self._status = "disconnected"
    self._last_error: str | None = None
    self._thread: threading.Thread | None = None

  @property
  def status(self) -> str:
    return self._status

  @property
  def last_error(self) -> str | None:
    return self._last_error

  def start(self) -> None:
    if not self.url:
      self._status = "disabled"
      return
    self._thread = threading.Thread(target=self._run, name="imu-bridge", daemon=True)
    self._thread.start()

  def stop(self) -> None:
    self._stop.set()

  def snapshot(self) -> dict[str, Any]:
    return {
      "status": self._status,
      "url": self.url,
      "rate_hz": self.rate_hz,
      "last_error": self._last_error,
    }

  def _run(self) -> None:
    try:
      import socketio
    except ImportError:
      self._status = "error"
      self._last_error = "python-socketio が未インストールです（pip install python-socketio）"
      _LOG.error(self._last_error)
      return

    while not self._stop.is_set():
      sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
      self._status = "connecting"
      self._last_error = None

      @sio.on("connect")
      def _on_connect() -> None:
        self._status = "connected"
        self._last_error = None
        hz = max(1.0, min(200.0, float(self.rate_hz)))
        sio.emit("imu/start", {"rate_hz": hz})

      @sio.on("disconnect")
      def _on_disconnect() -> None:
        if not self._stop.is_set():
          self._status = "disconnected"

      @sio.on("imu/sample")
      def _on_sample(payload: Any) -> None:
        if isinstance(payload, dict):
          self._app.ingest_imu(payload)

      @sio.on("imu/error")
      def _on_error(payload: Any) -> None:
        if isinstance(payload, dict) and payload.get("message"):
          self._last_error = str(payload["message"])
        else:
          self._last_error = str(payload)

      try:
        sio.connect(
          self.url,
          transports=["websocket"],
          wait_timeout=8,
        )
        while not self._stop.is_set() and sio.connected:
          time.sleep(0.2)
      except Exception as e:  # noqa: BLE001
        self._status = "error"
        self._last_error = str(e)
        _LOG.warning("IMU bridge connect failed (%s): %s", self.url, e)
      finally:
        try:
          if sio.connected:
            sio.emit("imu/stop")
        except Exception:  # noqa: BLE001
          pass
        try:
          sio.disconnect()
        except Exception:  # noqa: BLE001
          pass

      if self._stop.wait(2.0):
        break

    self._status = "disconnected"
