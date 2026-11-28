"""Serve the closed-take screen and its read API.

The process only reads the archive. It does not open USB, servos, or the
live hub. Start it on the machine that stays on and can see archive_root.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from take_view.router import router

DIST = Path(__file__).resolve().parent / "web" / "dist"
app = FastAPI(title="take-view")
app.include_router(router)


def _safe_file(path: str) -> Path | None:
    """A built asset inside dist. Anything else is the screen itself."""
    if not path or not DIST.is_dir():
        return None
    candidate = (DIST / path).resolve()
    root = DIST.resolve()
    if candidate == root or root not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


@app.get("/")
@app.get("/{path:path}")
def page(path: str = "") -> FileResponse:
    """The analysis screen. API routes are registered above this catch-all."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404)
    asset = _safe_file(path)
    if asset is not None:
        return FileResponse(asset)
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="web/dist is missing; build the screen first")
    return FileResponse(index)


def main() -> None:
    import uvicorn

    host = os.environ.get("TAKE_VIEW_HOST", "0.0.0.0")
    port = int(os.environ.get("TAKE_VIEW_PORT", "8780"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
