"""Decode CVI packed RAW12 to numerical evidence and an unprocessed gray BMP.

Packing follows Sipeed MaixPy examples/tools/bayer_to_tiff.py.
No crop, repair, denoise, or scene upload. Gray view uses fixed gain for comparison.
"""
import json
import struct
from pathlib import Path

for d in Path(__file__).resolve().parent.glob('linearraw*'):
    p = d / 'sensor-bayer.bin'
    if not p.exists():
        continue
    b = p.read_bytes()
    assert len(b) == 1280 * 720 * 3 // 2
    v = []
    for i in range(0, len(b), 3):
        v.extend([(b[i] << 4) | (b[i + 2] >> 4), (b[i + 1] << 4) | (b[i + 2] & 15)])
    result = {'case': d.name, 'width': 1280, 'height': 720,
              'first_8_row_max': [max(v[y * 1280:(y + 1) * 1280]) for y in range(8)],
              'raw_sha256': __import__('hashlib').sha256(b).hexdigest()}
    (d / 'bayer-metrics.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    out = bytearray()
    for y in reversed(range(720)):
        for x in range(1280):
            z = min(255, v[y * 1280 + x] // 4)
            out.extend([z, z, z])
    hdr = b'BM' + struct.pack('<IHHI', 54 + len(out), 0, 0, 54)
    hdr += struct.pack('<IiiHHIIiiII', 40, 1280, 720, 1, 24, 0, len(out), 0, 0, 0, 0)
    (d / 'bayer-gray.bmp').write_bytes(hdr + out)
    print(json.dumps(result))
