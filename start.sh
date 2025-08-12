#!/usr/bin/env bash
set -Eeuo pipefail

PORT="${PORT:-10000}"

# Health server để Render detect PORT + cho UptimeRobot ping
python - <<'PY' &
import os, http.server, socketserver
PORT = int(os.environ.get("PORT","10000"))

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # luôn 200 để healthcheck ok
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a, **k):  # quiet log
        pass

with socketserver.TCPServer(("0.0.0.0", PORT), H) as s:
    print(f"Health server listening on {PORT}", flush=True)
    s.serve_forever()
PY
HEALTH_PID=$!

cleanup(){ kill "$HEALTH_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# Chạy bot (đổi bot.py nếu entrypoint khác)
python -u bot_thuchi.py
