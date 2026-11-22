#!/bin/sh
# Serves the settings page on http://localhost:3000 (Web Serial needs localhost or
# https; Chrome / Edge). Whatever listens on the port is stopped first.
#
#   ./run.sh            then open http://localhost:3000  (add ?demo to try it without the module)
#   PORT=3001 ./run.sh  another port
set -eu
port=${PORT:-3000}
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

listeners() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port"/tcp 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true
    elif command -v ss >/dev/null 2>&1; then
        ss -H -ltnp "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true
    fi
}

pids=$(listeners)
if [ -n "$pids" ]; then
    echo "Port $port is in use: stopping PID $(echo $pids | tr '\n' ' ')"
    kill $pids 2>/dev/null || true
    n=0
    while [ -n "$(listeners)" ] && [ "$n" -lt 20 ]; do sleep 0.1; n=$((n + 1)); done
    pids=$(listeners)
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null || true
        sleep 0.3
    fi
    if [ -n "$(listeners)" ]; then
        echo "Could not free port $port (another user's process?)." >&2
        exit 1
    fi
fi

echo "32bit master settings page: http://localhost:$port   (demo without the module: http://localhost:$port/?demo)"
echo "Ctrl-C stops it."
# No caching, so an edited page or a regenerated demo.js is what the browser gets.
exec python3 -c '
import functools, http.server, sys

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

http.server.ThreadingHTTPServer.allow_reuse_address = True
server = http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), functools.partial(Handler, directory=sys.argv[2]))
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
' "$port" "$here"
