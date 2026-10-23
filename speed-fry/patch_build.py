from pathlib import Path
p=Path('/tmp/lrv-workspace/workspace/camera/build.sh')
s=p.read_text()
s=s.replace('"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c src/camera_bench.cpp -o build/bench.o','"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c src/camera_bench.cpp -o build/bench.o\n"$TC-g++" -std=c++11 "${FLAGS[@]}" "${INC[@]}" -c src/camera_stream.cpp -o build/stream.o')
needle='done\nfile bin/camera_bench*'
add='done\n"$TC-g++" -Wl,--dynamic-list=src/exports.list -Wl,--gc-sections -Wl,-rpath,\'$ORIGIN/../lib:/mnt/system/usr/lib:/mnt/system/usr/lib/3rd\' -Wl,-rpath-link,sdk/board-libs -Lsdk/board-libs -o bin/camera_stream build/stream.o build/atomic_compat.o build/common_*.o build/ini.o build/sensor_gc4653_cmos.o build/sensor_gc4653_sensor_ctl.o -Wl,--no-as-needed -lsys -lvpu -lvenc -lcvi_bin -lcvi_bin_isp -lisp -lisp_algo -lae -lawb -laf -lm -lpthread -ldl -latomic -static-libstdc++ -static-libgcc\nfile bin/camera_bench* bin/camera_stream'
s=s.replace(needle,add)
p.write_text(s)
