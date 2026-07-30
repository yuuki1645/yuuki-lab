"""HTTP API + MJPEG（ThreadingHTTPServer）。"""

from __future__ import annotations

import json
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from robot_recorder.app import RecorderApp
from robot_recorder.config import PACKAGE_ROOT

BOUNDARY = b"yuukiframe"
VIEWER_HTML = PACKAGE_ROOT / "viewer.html"
EXP_ID_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z_-]{0,63}$")


def _json_bytes(data: dict[str, Any]) -> bytes:
  return json.dumps(data, ensure_ascii=False).encode("utf-8")


def make_handler(app: RecorderApp):  # noqa: ANN201
  class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
      sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _cors(self) -> None:
      self.send_header("Access-Control-Allow-Origin", "*")
      self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
      self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, code: int, data: dict[str, Any]) -> None:
      body = _json_bytes(data)
      self.send_response(code)
      self._cors()
      self.send_header("Content-Type", "application/json; charset=utf-8")
      self.send_header("Content-Length", str(len(body)))
      self.send_header("Cache-Control", "no-store")
      self.end_headers()
      self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
      length = int(self.headers.get("Content-Length") or "0")
      raw = self.rfile.read(length) if length > 0 else b"{}"
      try:
        data = json.loads(raw.decode("utf-8"))
      except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(str(e)) from e
      if not isinstance(data, dict):
        raise ValueError("JSON object required")
      return data

    def do_OPTIONS(self) -> None:  # noqa: N802
      self.send_response(204)
      self._cors()
      self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
      parsed = urlparse(self.path)
      path = unquote(parsed.path)

      if path in ("/", "/index.html"):
        self._serve_viewer()
        return
      if path in ("/stream.mjpg", "/stream.mjpeg"):
        self._serve_mjpeg()
        return
      if path == "/api/status":
        self._send_json(200, app.status_dict())
        return
      if path == "/api/disk":
        d = app.check_disk()
        self._send_json(
          200,
          {
            "ok": True,
            "free_bytes": d.free_bytes,
            "total_bytes": d.total_bytes,
            "ok_for_record": d.ok_for_record,
            "warning": d.warning,
          },
        )
        return
      if path == "/api/experiments":
        active = app.store.get_active_experiment_id()
        items = []
        for exp in app.store.list_experiments():
          row = exp.to_dict()
          row["active"] = exp.id == active
          row["take_count"] = len(app.store.list_takes(exp.id))
          items.append(row)
        self._send_json(200, {"ok": True, "experiments": items, "active_experiment_id": active})
        return
      if path == "/api/imu/latest":
        sample = app.latest_imu()
        bridge = app.imu_bridge.snapshot() if app.imu_bridge else {"status": "disabled"}
        self._send_json(200, {"ok": True, "sample": sample, "imu_bridge": bridge})
        return
      if path.startswith("/data/"):
        self._serve_data(path[len("/data/") :])
        return

      m = re.match(r"^/api/experiments/([^/]+)$", path)
      if m:
        exp_id = m.group(1)
        exp = app.store.get(exp_id)
        if exp is None:
          self._send_json(404, {"ok": False, "error": "not_found"})
          return
        row = exp.to_dict()
        row["takes"] = app.store.list_takes(exp_id)
        row["active"] = exp_id == app.store.get_active_experiment_id()
        self._send_json(200, {"ok": True, "experiment": row})
        return

      self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
      parsed = urlparse(self.path)
      path = unquote(parsed.path)
      try:
        if path == "/api/record/start":
          code, data = app.start_recording()
          self._send_json(code, data)
          return
        if path == "/api/record/stop":
          code, data = app.stop_recording()
          self._send_json(code, data)
          return
        if path == "/api/ingest/command":
          payload = self._read_json()
          code, data = app.ingest_command(payload)
          self._send_json(code, data)
          return
        if path == "/api/ingest/imu":
          payload = self._read_json()
          code, data = app.ingest_imu(payload)
          self._send_json(code, data)
          return
        if path == "/api/experiments":
          body = self._read_json()
          exp = app.store.create(
            str(body.get("name") or ""),
            str(body["format_id"]) if body.get("format_id") else None,
          )
          self._send_json(201, {"ok": True, "experiment": exp.to_dict()})
          return

        m = re.match(r"^/api/experiments/([^/]+)/select$", path)
        if m:
          exp_id = m.group(1)
          if not EXP_ID_RE.match(exp_id):
            self._send_json(400, {"ok": False, "error": "bad_id"})
            return
          try:
            app.store.set_active_experiment_id(exp_id)
          except KeyError:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
          self._send_json(
            200,
            {"ok": True, "active_experiment_id": app.store.get_active_experiment_id()},
          )
          return
      except ValueError as e:
        self._send_json(400, {"ok": False, "error": "bad_json", "message": str(e)})
        return
      except OSError as e:
        self._send_json(400, {"ok": False, "error": "os_error", "message": str(e)})
        return

      self._send_json(404, {"ok": False, "error": "not_found"})

    def do_PATCH(self) -> None:  # noqa: N802
      parsed = urlparse(self.path)
      path = unquote(parsed.path)
      m = re.match(r"^/api/experiments/([^/]+)$", path)
      if not m:
        self._send_json(404, {"ok": False, "error": "not_found"})
        return
      exp_id = m.group(1)
      try:
        body = self._read_json()
        exp = app.store.rename(exp_id, str(body.get("name") or ""))
        self._send_json(200, {"ok": True, "experiment": exp.to_dict()})
      except KeyError:
        self._send_json(404, {"ok": False, "error": "not_found"})
      except ValueError as e:
        self._send_json(400, {"ok": False, "error": "bad_request", "message": str(e)})

    def do_DELETE(self) -> None:  # noqa: N802
      parsed = urlparse(self.path)
      path = unquote(parsed.path)
      m = re.match(r"^/api/experiments/([^/]+)$", path)
      if not m:
        self._send_json(404, {"ok": False, "error": "not_found"})
        return
      exp_id = m.group(1)
      try:
        app.store.delete(exp_id)
        self._send_json(200, {"ok": True})
      except KeyError:
        self._send_json(404, {"ok": False, "error": "not_found"})
      except OSError as e:
        self._send_json(409, {"ok": False, "error": "not_empty", "message": str(e)})

    def _serve_viewer(self) -> None:
      if not VIEWER_HTML.is_file():
        self._send_json(500, {"ok": False, "error": "viewer_missing"})
        return
      body = VIEWER_HTML.read_bytes()
      self.send_response(200)
      self._cors()
      self.send_header("Content-Type", "text/html; charset=utf-8")
      self.send_header("Content-Length", str(len(body)))
      self.end_headers()
      self.wfile.write(body)

    def _serve_mjpeg(self) -> None:
      self.send_response(200)
      self._cors()
      self.send_header(
        "Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}"
      )
      self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
      self.send_header("Pragma", "no-cache")
      self.send_header("Connection", "close")
      self.end_headers()
      last_seq = -1
      try:
        while True:
          seq, jpeg = app.wait_jpeg(last_seq, timeout=1.0)
          if jpeg is None or seq == last_seq:
            continue
          last_seq = seq
          header = (
            b"--"
            + BOUNDARY
            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode()
            + b"\r\n\r\n"
          )
          self.wfile.write(header)
          self.wfile.write(jpeg)
          self.wfile.write(b"\r\n")
          self.wfile.flush()
      except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
        return

    def _serve_data(self, rel: str) -> None:
      full = app.resolve_data_file(rel)
      if full is None:
        self.send_error(404)
        return
      ctype = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
      if full.suffix == ".m3u8":
        ctype = "application/vnd.apple.mpegurl"
      elif full.suffix == ".ts":
        ctype = "video/mp2t"
      data = full.read_bytes()
      self.send_response(200)
      self._cors()
      self.send_header("Content-Type", ctype)
      self.send_header("Content-Length", str(len(data)))
      self.send_header("Cache-Control", "no-cache")
      self.end_headers()
      self.wfile.write(data)

  return Handler


def run_server(app: RecorderApp, host: str, port: int) -> ThreadingHTTPServer:
  handler = make_handler(app)
  httpd = ThreadingHTTPServer((host, port), handler)
  return httpd
