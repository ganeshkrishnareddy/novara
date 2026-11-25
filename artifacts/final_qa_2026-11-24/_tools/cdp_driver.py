"""Minimal local Chrome DevTools Protocol driver for NOVARA QA.

Connects only to the locally launched Chrome on 127.0.0.1:9222. No external
network access. Every evaluated expression and observed result is returned to
the caller for logging.
"""
from __future__ import annotations

import base64
import itertools
import json
import time
from pathlib import Path

import httpx
import websocket

BASE_PORT = 9222
URL_MATCH = "127.0.0.1:8765"


class CDP:
    def __init__(self, port: int = BASE_PORT, url_match: str = URL_MATCH):
        targets = httpx.get(f"http://127.0.0.1:{port}/json", timeout=10).json()
        pages = [t for t in targets if t.get("type") == "page" and url_match in t.get("url", "")]
        if not pages:
            raise RuntimeError(f"No local NOVARA page found in CDP targets: {[t.get('url') for t in targets]}")
        self.target = pages[0]
        self.ws = websocket.create_connection(self.target["webSocketDebuggerUrl"], timeout=20)
        self._ids = itertools.count(1)

    def call(self, method: str, params: dict | None = None):
        mid = next(self._ids)
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expression: str, await_promise: bool = True):
        result = self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": await_promise,
            "returnByValue": True,
        })
        if "exceptionDetails" in result:
            raise RuntimeError(json.dumps(result["exceptionDetails"], ensure_ascii=False)[:500])
        return result.get("result", {}).get("value")

    def navigate(self, url: str, settle: float = 1.2):
        self.call("Page.enable")
        self.call("Page.navigate", {"url": url})
        time.sleep(settle)
        return self.js("location.href")

    def hash(self, route: str, settle: float = 0.8):
        self.js(f"location.hash={json.dumps(route)}")
        time.sleep(settle)
        return self.js("location.href")

    def screenshot(self, path: str | Path):
        self.call("Page.enable")
        shot = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(base64.b64decode(shot["data"]))
        return str(p)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
