"""FastAPI + Socket.IO 中継サーバー（React SPA を同ポートで配信）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import socketio
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

CLIENT_DIR = PROJECT_ROOT / "dist" / "client"

latest_frame: bytes | None = None

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    max_http_buffer_size=10 * 1024 * 1024,
)


@sio.event
async def connect(sid, _environ):
    if latest_frame is not None:
        await sio.emit("frame_update", latest_frame, to=sid)


@sio.on("camera_frame")
async def camera_frame(sid, data):
    global latest_frame
    buf = _to_bytes(data)
    if not buf:
        return
    latest_frame = buf
    await sio.emit("frame_update", buf, skip_sid=sid)


def _to_bytes(data: object) -> bytes | None:
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    return None


fastapi_app = FastAPI(title="iphone-camera-relay", docs_url=None, redoc_url=None)


@fastapi_app.get("/")
async def index():
    return _spa_index()


@fastapi_app.get("/{full_path:path}")
async def spa(full_path: str):
    if full_path.startswith("socket.io"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if not CLIENT_DIR.is_dir():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "dist/client がありません。プロジェクトルートで npm run build を実行してください。",
            },
        )
    candidate = CLIENT_DIR / full_path
    try:
        candidate.resolve().relative_to(CLIENT_DIR.resolve())
    except ValueError:
        return _spa_index()
    if candidate.is_file():
        return FileResponse(candidate)
    return _spa_index()


def _spa_index() -> FileResponse | JSONResponse:
    index = CLIENT_DIR / "index.html"
    if not index.is_file():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "dist/client/index.html がありません。npm run build を実行してください。",
            },
        )
    return FileResponse(index)


socket_app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


def run() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "5000"))
    key = PROJECT_ROOT / "key.pem"
    cert = PROJECT_ROOT / "cert.pem"
    ssl_config: dict = {}
    if key.is_file() and cert.is_file():
        ssl_config = {"ssl_keyfile": str(key), "ssl_certfile": str(cert)}
        scheme = "https"
    else:
        print(
            "[camera-relay] cert.pem / key.pem が見つかりません。HTTP で起動します。",
        )
        print(
            "[camera-relay] iPhone のカメラ利用には HTTPS が必要なため、"
            "ルートに cert.pem と key.pem を配置してください。",
        )
        scheme = "http"

    print(
        f"[camera-relay] {scheme}://0.0.0.0:{port} （LAN からは PC の IP でアクセス）",
    )
    print(f"[camera-relay] iPhone: {scheme}://<PCのIP>:{port}/camera")
    print(f"[camera-relay] PC表示: {scheme}://<PCのIP>:{port}/monitor")

    reload = os.environ.get("DEV_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "backend.main:socket_app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        **ssl_config,
    )


if __name__ == "__main__":
    run()
