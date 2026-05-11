# type: ignore

"""IMU サンプルをメモリに溜め、一定間隔で CSV に追記する。"""

from __future__ import annotations

import csv
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

CSV_COLUMNS = [
    "wall_unix",
    "perf_timestamp",
    "mock",
    "accel_x",
    "accel_y",
    "accel_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "angle_pitch",
    "angle_roll",
    "angle_yaw",
]


def _flatten_imu_sample(sample: dict[str, Any]) -> list[Any]:
    acc = sample.get("accel") or {}
    gyr = sample.get("gyro") or {}
    ang = sample.get("angle") or {}
    return [
        time.time(),
        sample.get("timestamp"),
        bool(sample.get("mock")),
        acc.get("x"),
        acc.get("y"),
        acc.get("z"),
        gyr.get("x"),
        gyr.get("y"),
        gyr.get("z"),
        ang.get("pitch"),
        ang.get("roll"),
        ang.get("yaw"),
    ]


class ImuCsvLog:
    """バッファリング後に CSV へ追記。スレッドセーフ。"""

    def __init__(
        self,
        *,
        log_dir: Path | None,
        flush_interval_sec: float = 10.0,
    ) -> None:
        self._log_dir = log_dir
        self._flush_interval_sec = max(0.5, float(flush_interval_sec))
        self._lock = threading.Lock()
        self._buffer: list[list[Any]] = []
        self._file_path: Path | None = None
        self._header_written = False
        self._last_flush_monotonic = 0.0

    @property
    def enabled(self) -> bool:
        return self._log_dir is not None

    def is_recording(self) -> bool:
        """現在 CSV セッションが開いているか（``begin_session`` 済みで未 ``end_session``）。"""
        with self._lock:
            return self._file_path is not None

    def begin_session(self) -> None:
        """新しいストリーム開始時。未フラッシュ分を吐き出し、新しい CSV ファイルを用意する。"""
        self.flush()
        if not self.enabled:
            return
        with self._lock:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            name = time.strftime("imu_%Y%m%d_%H%M%S.csv")
            self._file_path = self._log_dir / name
            self._header_written = False
            self._last_flush_monotonic = time.monotonic()

    def end_session(self) -> None:
        """ストリーム停止時。残りを書き込み、セッションを閉じる。"""
        self.flush()
        with self._lock:
            self._file_path = None
            self._header_written = False

    def record_sample(self, sample: dict[str, Any]) -> None:
        """1 サンプルをバッファへ追加し、間隔を超えていればディスクへ追記する。"""
        if not self.enabled:
            return
        row = _flatten_imu_sample(sample)
        rows_to_write: list[list[Any]] | None = None
        with self._lock:
            if self._file_path is None:
                return
            self._buffer.append(row)
            now = time.monotonic()
            if now - self._last_flush_monotonic >= self._flush_interval_sec:
                rows_to_write = self._buffer
                self._buffer = []
                self._last_flush_monotonic = now
        if rows_to_write:
            self._append_rows_unlocked(rows_to_write)

    def flush(self) -> None:
        """バッファをすべてファイルへ書き出す。"""
        rows_to_write: list[list[Any]] | None = None
        with self._lock:
            if self._buffer:
                rows_to_write = self._buffer
                self._buffer = []
        if rows_to_write:
            self._append_rows_unlocked(rows_to_write)

    def _append_rows_unlocked(self, rows: list[list[Any]]) -> None:
        if not rows:
            return
        with self._lock:
            path = self._file_path
            if path is None:
                return
            need_header = not self._header_written
            if need_header:
                self._header_written = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if need_header:
                    w.writerow(CSV_COLUMNS)
                w.writerows(rows)
        except OSError as e:
            _LOG.warning("IMU CSV 書き込みに失敗しました: %s", e)


def imu_csv_log_from_env() -> ImuCsvLog:
    """
    環境変数から ``ImuCsvLog`` を構築する。

    - ``IMU_LOG_DISABLE`` … 1/true/on なら ``log_dir=None``（記録しない）
    - ``IMU_LOG_DIR`` … 出力ディレクトリ（未設定または空なら ``./imu_logs``）
    - ``IMU_LOG_FLUSH_SEC`` … フラッシュ間隔（秒、既定 10）
    """
    val = os.environ.get("IMU_LOG_DISABLE", "").lower()
    if val in ("1", "true", "yes", "on"):
        return ImuCsvLog(log_dir=None)

    raw_dir = os.environ.get("IMU_LOG_DIR", "./imu_logs").strip()
    if not raw_dir:
        return ImuCsvLog(log_dir=None)

    flush_raw = os.environ.get("IMU_LOG_FLUSH_SEC", "10").strip()
    try:
        flush_sec = float(flush_raw) if flush_raw else 10.0
    except ValueError:
        flush_sec = 10.0

    return ImuCsvLog(log_dir=Path(raw_dir).resolve(), flush_interval_sec=flush_sec)
