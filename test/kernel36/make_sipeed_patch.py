#!/usr/bin/env python3
"""Create reviewable git-compatible patch against Sipeed BSP 2026-01-14."""
from pathlib import Path
import difflib
base=Path(__file__).resolve().parent
cases=[
("osdrv/interdrv/v2/cif/chip/mars/cif.c","board_reference/cif.sipeed.c","sipeed_patch-src/cif.c"),
("osdrv/interdrv/v2/include/chip/mars/uapi/linux/cif_uapi.h","board_reference/cif_uapi.sipeed.h","sipeed_patch-src/cif_uapi.h")
]
patch=[]
for relative,old,new in cases:
    original=(base/old).read_text(encoding="utf8").splitlines(keepends=True)
    edited=(base/new).read_text(encoding="utf8").splitlines(keepends=True)
    patch.extend(difflib.unified_diff(original,edited,fromfile="a/"+relative,tofile="b/"+relative))
destination=base/"sipeed_soph_mipi_rx_36mhz.patch"
with destination.open("w",encoding="utf8",newline="\n") as stream:
    stream.write("".join(patch))
print("patch:",destination,"lines:",len(patch),"bytes:",destination.stat().st_size)
