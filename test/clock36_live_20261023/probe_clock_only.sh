#!/bin/sh
# SG2002 CAM1 clock-only test. No stream. Safe rollback with shell EXIT trap.
set -eu
REG=0x030028c4
ORIGINAL=''
ARMED=0
cleanup() {
    rc=$?
    trap - 0 1 2 15
    if [ "$ARMED" = 1 ]; then
        echo "RESTORING_CAM1=$ORIGINAL"
        devmem "$REG" 32 "$ORIGINAL" || echo RESTORE_WRITE_FAILED
        echo "RESTORE_RAW=$(devmem "$REG" 32)"
        echo "RESTORE_CLOCK=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
    fi
    exit "$rc"
}
trap cleanup 0 1 2 15
echo "KERNEL=$(uname -r)"
test "$(uname -r)" = '5.10.4-tag-'
test ! -d /code/camera/run/lock
if pidof camera_preview_hd camera_preview80 camera_preview_factory camera_factory_timing camera_bench camera_http80 camera_normal60 camera_stream minraw36 minraw1080_27or36 sensor_test sample_vio >/dev/null 2>&1; then
    echo CAMERA_BUSY_ABORT
    exit 4
fi
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
echo "TEMP_MC=$TEMP"
test "$TEMP" -lt 75000
ORIGINAL=$(devmem "$REG" 32)
echo "ORIGINAL_RAW=$ORIGINAL"
test "$ORIGINAL" = '0x00200001'
PARENT=$(cat /sys/kernel/debug/clk/clk_cam0pll/clk_rate)
echo "PARENT_HZ=$PARENT"
test "$PARENT" -gt 1187000000
test "$PARENT" -lt 1189000000
echo "ORIGINAL_CLOCK=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
echo "CLOCK_ENABLE_COUNT=$(cat /sys/kernel/debug/clk/clk_cam1/clk_enable_count)"
ARMED=1
echo "TEST_SET_CAM1_DIVIDER_33"
devmem "$REG" 32 0x00210001
echo "TEST_RAW=$(devmem "$REG" 32)"
echo "TEST_CLOCK=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
sleep 2
echo "TEST_CLOCK_AFTER_2S=$(cat /sys/kernel/debug/clk/clk_cam1/clk_rate)"
echo "TEST_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)"
echo "TEST_MIPI=$(awk '/^[ ]*0[ ]+[0-9]+[ ]+[0-9]+/{print;exit}' /proc/mipi-rx)"
