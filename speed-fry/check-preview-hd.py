"""Bounded live MJPEG receive test, without image-library dependencies."""
from pathlib import Path
import hashlib
import json
import struct
import time
import urllib.request
import argparse

p = argparse.ArgumentParser()
p.add_argument('--seconds', type=float, default=10)
p.add_argument('--host', choices=['10.133.125.1', '10.133.124.1'], default='10.133.125.1')
a = p.parse_args()
root = Path(__file__).resolve().parent
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
count = 0
hashes = set()
first = last = None
buf = b''
def dimensions(jpeg):
    i = 2
    while i + 4 < len(jpeg):
        if jpeg[i] != 255:
            raise ValueError('Invalid JPEG marker')
        marker = jpeg[i+1]
        length = int.from_bytes(jpeg[i+2:i+4], 'big')
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack('>HH', jpeg[i+5:i+9])
            return w, h
        i += 2 + length
    raise ValueError('No JPEG SOF')

with opener.open('http://' + a.host + ':8081/live.mjpg', timeout=15) as r:
    content_type = r.headers.get('Content-Type')
    while first is None or time.monotonic() - first < a.seconds:
        chunk = r.read(16384)
        if not chunk:
            break
        buf += chunk
        while True:
            start = buf.find(b'\xff\xd8')
            end = buf.find(b'\xff\xd9', max(start, 0))
            if start < 0 or end < 0:
                break
            jpg, buf = buf[start:end+2], buf[end+2:]
            t = time.monotonic()
            if first is None:
                first = t
                width, height = dimensions(jpg)
                (root / 'preview-hd-first.jpg').write_bytes(jpg)
            count += 1
            hashes.add(hashlib.sha256(jpg).hexdigest())
            last = t
            last_jpg = jpg
if count < 2:
    raise RuntimeError(f'Not enough frames: {count}')
(root / 'preview-hd-last.jpg').write_bytes(last_jpg)
result = dict(host=a.host, content_type=content_type, width=width, height=height, frames=count,
              receive_fps=(count-1)/(last-first), seconds=last-first, distinct_jpeg_hashes=len(hashes))
(root / 'preview-hd-receive.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
