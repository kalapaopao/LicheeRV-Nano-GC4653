"""Read MJPEG for ten seconds; save first/last JPEG and measured receive rate."""
from pathlib import Path
import hashlib
import json
import time
import urllib.request

root = Path(__file__).resolve().parent
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
frames = 0
hashes = set()
start = first = last = None
buffer = b''
with opener.open('http://10.133.125.1:8080/live.mjpg', timeout=15) as r:
    content_type = r.headers.get('Content-Type')
    while start is None or time.monotonic() - start < 10:
        chunk = r.read(4096)
        if not chunk:
            break
        buffer += chunk
        while True:
            a = buffer.find(b'\xff\xd8')
            b = buffer.find(b'\xff\xd9', max(a, 0))
            if a < 0 or b < 0:
                break
            jpeg, buffer = buffer[a:b+2], buffer[b+2:]
            t = time.monotonic()
            if start is None:
                start = first = t
                (root / 'preview80-first.jpg').write_bytes(jpeg)
            last = t
            frames += 1
            hashes.add(hashlib.sha256(jpeg).hexdigest())
            last_jpeg = jpeg
if frames < 2:
    raise RuntimeError(f'Not enough frames: {frames}')
(root / 'preview80-last.jpg').write_bytes(last_jpeg)
result = dict(content_type=content_type, frames=frames, seconds=last-first,
              receive_fps=(frames-1)/(last-first), distinct_jpeg_hashes=len(hashes))
(root / 'preview80-receive.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
