import os
import urllib.request

with urllib.request.urlopen(f"http://127.0.0.1:{os.environ.get('APP_PORT', '2112')}/health", timeout=3) as response:
    if response.status != 200 or response.read() != b'{"status":"ok"}\n':
        raise SystemExit(1)
