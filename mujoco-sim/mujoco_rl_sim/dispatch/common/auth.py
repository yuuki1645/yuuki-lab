"""API トークン検証。"""

from __future__ import annotations

from flask import Request


def check_token(request: Request, expected: str | None) -> bool:
  if not expected:
    return True
  got = request.headers.get("X-Dispatch-Token", "")
  return got == expected
