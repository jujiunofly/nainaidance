#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
PORT = int(os.environ.get("PORT", "8080"))
MAX_MESSAGE_LENGTH = 500


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {
                "ok": True,
                "telegramConfigured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            })
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "Not found"})
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path != "/api/notify":
            self._json(404, {"ok": False, "error": "Not found"})
            return
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            self._json(503, {"ok": False, "error": "Telegram is not configured"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 4096:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            message = str(payload.get("message", "")).strip()
            if not message or len(message) > MAX_MESSAGE_LENGTH:
                raise ValueError("Invalid message")
            self._send_telegram(message)
            self._json(200, {"ok": True})
        except ValueError as error:
            self._json(400, {"ok": False, "error": str(error)})
        except Exception as error:
            print(f"Telegram notification failed: {error}", file=sys.stderr)
            self._json(502, {"ok": False, "error": "Telegram send failed"})

    def _send_telegram(self, message):
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram HTTP {error.code}: {detail}") from error

        result = json.loads(raw)
        if not result.get("ok"):
            raise RuntimeError("Telegram rejected the message")

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    if not PUBLIC_DIR.exists():
        raise SystemExit(f"Missing public directory: {PUBLIC_DIR}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), AppHandler)
    print(f"Serving nainaidance on http://0.0.0.0:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
