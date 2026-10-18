#!/usr/bin/env python3
import json
import os
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
RECORDS_FILE = DATA_DIR / "records.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
PORT = int(os.environ.get("PORT", "8080"))
MAX_MESSAGE_LENGTH = 500
MAX_BODY_BYTES = 1_000_000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STORE_LOCK = threading.Lock()


def is_valid_date_key(key):
    if not DATE_RE.fullmatch(key):
        return False
    try:
        datetime.strptime(key, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def positive_int(value, default=None):
    try:
        number = int(value)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


def sanitize_record(value, key):
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    if status not in ("yes", "no"):
        return None

    updated_at = positive_int(value.get("updatedAt"), None)
    if updated_at is None:
        updated_at = int(datetime.strptime(key, "%Y-%m-%d").replace(hour=12).timestamp() * 1000)

    toilet_at = None
    time_known = False
    if status == "yes":
        toilet_at = positive_int(value.get("toiletAt"), None)
        if toilet_at is None:
            toilet_at = updated_at
            time_known = False
        else:
            time_known = value.get("timeKnown") is not False

    return {
        "status": status,
        "updatedAt": updated_at,
        "toiletAt": toilet_at,
        "timeKnown": time_known,
    }


def load_records_locked():
    if not RECORDS_FILE.exists():
        return {}
    try:
        data = json.loads(RECORDS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read records file: {error}", file=sys.stderr)
        return {}

    source = data.get("records", data) if isinstance(data, dict) else {}
    if not isinstance(source, dict):
        return {}

    records = {}
    for key, value in source.items():
        if not isinstance(key, str) or not is_valid_date_key(key):
            continue
        clean = sanitize_record(value, key)
        if clean:
            records[key] = clean
    return records


def save_records_locked(records):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = RECORDS_FILE.with_suffix(".tmp")
    payload = {"version": 3, "records": records}
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, RECORDS_FILE)


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {
                "ok": True,
                "telegramConfigured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
                "storageWritable": os.access(DATA_DIR, os.W_OK),
            })
            return
        if path == "/api/records":
            with STORE_LOCK:
                records = load_records_locked()
            self._json(200, {"ok": True, "records": records})
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "Not found"})
            return
        super().do_GET()

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/notify":
            self._handle_notify()
            return
        if path == "/api/records":
            self._handle_records()
            return
        self._json(404, {"ok": False, "error": "Not found"})

    def _handle_notify(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            self._json(503, {"ok": False, "error": "Telegram is not configured"})
            return
        try:
            payload = self._read_json(4096)
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

    def _handle_records(self):
        try:
            payload = self._read_json(MAX_BODY_BYTES)
            action = payload.get("action", "set")

            with STORE_LOCK:
                records = load_records_locked()
                if action == "set":
                    key = str(payload.get("date", ""))
                    if not is_valid_date_key(key):
                        raise ValueError("Invalid date")
                    clean = sanitize_record(payload.get("record"), key)
                    if not clean:
                        raise ValueError("Invalid record")
                    records[key] = clean
                elif action == "delete":
                    key = str(payload.get("date", ""))
                    if not is_valid_date_key(key):
                        raise ValueError("Invalid date")
                    records.pop(key, None)
                elif action == "clear":
                    records = {}
                elif action == "import":
                    incoming = payload.get("records")
                    if not isinstance(incoming, dict):
                        raise ValueError("Invalid import data")
                    clean_records = {}
                    for key, value in incoming.items():
                        if not isinstance(key, str) or not is_valid_date_key(key):
                            continue
                        clean = sanitize_record(value, key)
                        if clean:
                            clean_records[key] = clean
                    if not clean_records:
                        raise ValueError("No valid records to import")
                    records.update(clean_records)
                else:
                    raise ValueError("Unknown action")

                save_records_locked(records)

            self._json(200, {"ok": True, "records": records})
        except ValueError as error:
            self._json(400, {"ok": False, "error": str(error)})
        except Exception as error:
            print(f"Record storage failed: {error}", file=sys.stderr)
            self._json(500, {"ok": False, "error": "Record storage failed"})

    def _read_json(self, max_bytes):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid request size") from error
        if length <= 0 or length > max_bytes:
            raise ValueError("Invalid request size")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON body") from error

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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
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
