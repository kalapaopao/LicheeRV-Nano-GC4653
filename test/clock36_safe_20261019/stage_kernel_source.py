#!/usr/bin/env python3
"""Isolated snapshot of already-checked-out Linux source for Kbuild experiments.
Source remains untouched. All snapshots/line-ending fixes under test/clock36_safe_20261019.
"""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
SRC=ROOT.parent/"vendor_linux"
DST=ROOT/"kernel_src"
if not DST.exists():
    DST.mkdir()
for name in ("arch","include","scripts","drivers"):
    if name in ("arch","include") and (DST/name).exists():
        print("Verified previous copy phase exists; resume after",name,flush=True)
        continue
    print("Copy",name,flush=True)
    shutil.copytree(SRC/name,DST/name,symlinks=False,dirs_exist_ok=True)
for name in ("Makefile","Kbuild","Kconfig","README"):
    if (SRC/name).is_file():
        shutil.copy2(SRC/name,DST/name)
normalized=[]
for path in (DST/"scripts").rglob("*"):
    if not path.is_file() or path.stat().st_size>500000:
        continue
    if path.suffix in (".sh",".pl") or path.name in ("mkmakefile","setlocalversion","checkstack.pl","gcc-version.sh"):
        body=path.read_bytes()
        if body.count(b"\r\n")>0:
            path.write_bytes(body.replace(b"\r\n",b"\n"))
            normalized.append(str(path.relative_to(DST)))
print("Source snapshot saved",DST,"normalizations",len(normalized),flush=True)
(ROOT/"logs"/"normalized_scripts.txt").write_text("\n".join(normalized),encoding="utf8")
