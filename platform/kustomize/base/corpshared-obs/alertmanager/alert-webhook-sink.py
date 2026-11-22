#!/usr/bin/env python3
"""Minimal Alertmanager webhook receiver: logs one line per alert and answers 200 (backlog item 48).

It is the default destination of the Alertmanager webhook until a real endpoint is configured
(scripts/set_alertmanager_webhook.sh). Standard library only; the alert payload is only logged, never executed.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/healthz" else 404)
        self.end_headers()
        if self.path == "/healthz":
            self.wfile.write(b"ok")

    def do_POST(self):
        if self.path != "/alerts":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 1_000_000)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as exc:  # malformed request: say so, do not crash
            self.send_response(400)
            self.end_headers()
            print(f"WEBHOOK bad request: {exc}", flush=True)
            return
        for alert in payload.get("alerts", []):
            labels, notes = alert.get("labels", {}), alert.get("annotations", {})
            print("ALERT status=%s severity=%s alertname=%s service=%s summary=%r startsAt=%s" % (
                alert.get("status"), labels.get("severity", "-"), labels.get("alertname", "-"),
                labels.get("service", "-"), notes.get("summary", ""), alert.get("startsAt", "")), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):  # the default access log would repeat the alert lines
        pass


if __name__ == "__main__":
    print("alert-webhook-sink listening on :8080", flush=True)
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
