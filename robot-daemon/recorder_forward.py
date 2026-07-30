"""サーボ指令ログをメイン PC の robot-recorder へ非同期送信する。

制御応答を待たせない。失敗時は諦める（バッファなし）。
環境変数 ``RECORDER_URL``（例: http://192.168.100.20:8766）。未設定なら送信しない。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

_LOG = logging.getLogger(__name__)

try:
    import urllib.request
except ImportError:  # pragma: no cover
    urllib = None  # type: ignore


def _recorder_base() -> str | None:
    raw = (os.environ.get("RECORDER_URL") or "").strip().rstrip("/")
    return raw or None


def forward_command_async(payload: dict[str, Any]) -> None:
    """裏スレッドで POST /api/ingest/command。例外は握りつぶす。"""
    base = _recorder_base()
    if not base:
        return

    def _worker() -> None:
        url = base + "/api/ingest/command"
        body = dict(payload)
        body.setdefault("forwarded_at_unix", time.time())
        try:
            import json

            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                resp.read()
        except Exception as e:  # noqa: BLE001 — 失敗は捨てる
            _LOG.debug("recorder command forward failed: %s", e)

    threading.Thread(target=_worker, name="recorder-cmd", daemon=True).start()
