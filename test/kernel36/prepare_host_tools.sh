#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/d/study/LicheeRV/test/kernel36/host_tools
mkdir -p "$ROOT/downloads" "$ROOT/sysroot"
cd "$ROOT/downloads"
# Local portable extraction. Do NOT install into WSL /usr or write outside project test.
for pkg in make gcc-11 cpp-11 gcc-11-base libgcc-11-dev libc6-dev linux-libc-dev libgmp10 libmpfr6 libmpc3 libisl23 libzstd1 zlib1g libcc1-0 binutils; do
  if ! ls "${pkg}"_*.deb >/dev/null 2>&1; then
    echo "Download $pkg"
    apt-get download "$pkg"
  fi
done
for f in ./*.deb; do dpkg-deb -x "$f" "$ROOT/sysroot"; done
printf 'Portable binaries:\n'
find "$ROOT/sysroot/usr/bin" -maxdepth 1 -name '*gcc*' -o -name make -o -name 'cpp*' 2>/dev/null
