# 开发交接说明

## 当前状态
本次仅整理本地文件、重新编译、验证打包，不连接新设备、不刷机、不修改板端配置，也不继续新超频实验。
原工程和原始记录保持原样。源码来自当前工作副本，未读取 Git 历史，不能据此声称对应某个上游提交。
实测日期为 2026-10-07，打包与重编译日期为 2026-10-18；此次没有重新采集摄像头画面。

| 入口 | 画幅 | 实测 FPS | 测量范围 |
|---|---|---|---|
| 30 | 2560×1440 | 30.0004 | 8 秒 / 241 帧 |
| 60 | 1280×720 | 59.9000 | 20 秒 / 1199 帧 |
| 80 | 1280×720 | 82.3335 | 60 秒 / 4941 帧 |
| 80-empty | 1280×720 | 82.4994 | 20 秒 / 1651 帧 |

80 档 60 秒有 9 次超过 1.8/80 秒的相邻 PTS 间隔，不是零抖动保证。空跑只有 20 秒记录，不能证明数小时稳定性。
PTS 递增不单独证明每帧光学内容不同；暗画面、有效曝光与运动成像尚未验收。
未验证：温升长期压力、双目同步、VIO、实时编码/传输、其他板卡/镜像/传感器。

## 原位置与系统依赖
- 原主机：/home/admin123/projects/LicheeRV/crossCompiling/camera，SDK 在同级 LicheeRV-Nano-Build。
- 原板：/code/camera；原系统：Linux 5.10.4，riscv64，SG2002。
- 系统配置：/mnt/data/sensor_cfg.ini；系统库：/mnt/system/usr/lib 与 /mnt/system/usr/lib/3rd，均未覆盖。
- 配套系统需有对应 CVI/ISP/AE/AWB 库、PQ/tuning 数据、内核接口与设备节点，本包不是完整镜像。
- 旧 Windows SSH/Paramiko 辅助工具依赖旧路径，没有复制进包。板端采集不依赖电脑常驻。
- 旧后台菜单脚本曾刷出约 62GB 日志，本包不带旧启动器。不要把交互 sensor_test 的 stdin 接 /dev/null 后后台循环。

## 主机环境与构建
要求 x86_64 Linux；已验证 Ubuntu 22.04 WSL2，Xuantie riscv64-unknown-linux-musl GCC 10.2.0。
目标解释器 /lib/ld-musl-riscv64xthead.so.1，静态链接 libstdc++/libgcc，动态使用原板 CVI 系统库。
ARM Mac、ARM Linux 无法直接运行这个 x86_64 编译器。

主机需 bash、file、tar、gzip、sha256sum；离线报告检查用 python3。本次没有安装新依赖。
若编译器提示缺宿主动态库，用 ldd 检查 gcc、libexec 中的 cc1/cc1plus，根据新电脑报错补齐 Ubuntu 22.04 宿主库，例如 libgmp/libmpfr/libmpc/zlib。
不要把板端 .so 放到宿主 LD_LIBRARY_PATH。

camera 与 LicheeRV-Nano-Build 同级，在 camera 根目录执行：
~~~bash
bash build.sh
bash build-empty.sh
~~~
前一步生成正常、原驱动基线、AE诊断版；后一步复用编译对象，构建空跑版。
build/ 和 experiments/over100/build/ 为本机新产物，归档不含旧 .o。
如需仅编译所有历史实验：
~~~bash
bash experiments/over100/build.sh
~~~
编译成功不等于这些失败 ROI 模式已能采集。

裁剪 SDK 含：完整官方工具链目录、middleware/v2/include、两组 uapi、inih 源码与许可证。
不含内核源码、完整 BSP 构建系统或固件镜像。
sdk/board-libs 是原板库的链接副本，不能直接覆盖新镜像的系统库。
原工作目录的通用 GNU/glibc Dockerfile 未作为有效构建环境交付，Docker 引擎此前无法连接，容器构建没有验证成功。

## 脚本和程序
| 文件 | 用途 |
|---|---|
| camera_bench | MaixCDK 驱动，30/60/80 参数 |
| camera_bench_baseline | 原驱动基线，推荐只用 30 |
| camera_bench_empty | 空跑版，推荐 80 |
| camera_bench_ae_fix | 当前模式 AE 默认值诊断 |
| camera_bench_roi* | 部分没有输出的 ROI 实验 |
| camera_bench_factory1080 | Ingenic 1080P 表移植，曾测 67.04FPS，实验用途 |

scripts/benchmark.sh 管理互斥、PID、日志、退出清理。迁移包仅增加 80-empty 分支；原入口保留。
scripts/stop.sh 核对受管进程路径再发 TERM；不要 kill -9。
板端入口固定 /code/camera，不能只移动目录后照旧运行。主机目录可变，camera 与 SDK 相对位置需保持。
初始化、4 秒热身、样本保存和清理不在指定统计时长内，所以总耗时更长。
常规版循环写 frames.csv，会有文件缓存开销；源码顶部“no disk work”注释不够准确，以代码为准。
空跑版不逐帧写 CSV，但计时后仍保存一张 NV21，不是持续录像程序。
原基准在零帧情况下可能返回 0，验收必须检查 JSON；不能只看进程退出码。
CPU percent 是进程 CPU 时间/墙钟时间，包含同进程线程，不是系统总负载。

## SSH、安装与回退
IP 会变，Windows USB 网卡自身地址不等于板端地址。用原串口、路由器或 USB 子网邻居信息确认板子。
不随包保存密码、私钥、known_hosts；使用自己的设备凭据：
~~~bash
ssh root@板端IP
~~~
同一原板无需刷机，已有 /code/camera 可直接执行原 80 档。若需安装迁移包：
~~~bash
scp board-runtime.tar.gz install-board.sh root@板端IP:/tmp/
ssh root@板端IP
cd /tmp
sh install-board.sh
~~~
如果旧 sshd 缺 SFTP 子系统，可按具体报错使用 scp -O。安装器遇到 /code/camera 存在会拒绝覆盖。
要更新已有目录：先正常停止并核实无其他摄像头进程，把旧 /code/camera 改名为 /code 下唯一备份目录，再运行安装器；这些步骤不由本次打包自动执行。
回退：停止新程序、保留新目录、恢复旧目录为 /code/camera。旧报告留在旧备份中，不自动合并或删除。

无需把系统 sensor_cfg.ini 改名为 80FPS；程序按参数在内存切换模式。configs/sensor_cfg.original.ini 仅供参考，不自动覆盖。
新板的 I2C、lane、MCLK 接线和镜像须实际核实。刷镜像前自行备份原 SD 卡；本包不含标定或系统镜像。

## 验收
板端：
~~~sh
cd /code/camera
sh scripts/benchmark.sh 30 8
sh scripts/benchmark.sh 80 60
sh scripts/benchmark.sh 80-empty 20
~~~
30 档预期约 30FPS，80 档原板约 82FPS；frames>0、duplicate_pts=0、timeouts=0，host/PTS FPS 接近。
新环境受镜像、供电、光照/AE 影响，不承诺与历史数值完全相同。
把 result.json 拷回电脑可检查：
~~~bash
python3 tools/check-results.py /实际路径/result.json --min-fps 75
~~~
这只检查数值，不代替画质与长稳测试。

日志位置：
- result.json：requested_fps 是请求值，host_fps 和 pts_fps 才是本次实际计数。
- frames.csv：正常版每帧 PTS，空跑版不生成。
- before/after-vi*.txt：VI/CSI 计数，前后相减看变化。
- run.log：初始化、AE、VTS、释放；正常退出有 Free pa。
- memory-before/after.txt：原板约 83~84 MB 可用，仅作该镜像参考。
- exit-code.txt：退出状态，仍需检查 JSON。

常见故障：
1. ELF 文件在却提示不存在：核实 RISC-V/musl 解释器，不要换 glibc 编译器试错。
2. __sync_fetch_and_add_1 / __sync_fetch_and_and_1 解析失败：保留 atomic_compat.c、exports.list 和链接选项，不要用 -rdynamic 替代或替换系统 libisp.so。
3. lock exists：先 status.sh/stop.sh 确认真进程。异常残留锁也应在核实无采集后人工处理，不能直接删锁并重复启动。
4. 零帧/超时：看 I2C/lane/初始化/CSI，不能只把请求 FPS 改大。
5. 黑暗画面：固定明亮场景先做 30 档对照，再检查高速曝光/画质。
6. 看图：make_preview.sh 依赖板端 ffmpeg；不存在时可将 NV21 复制电脑后转换，不影响采集。
~~~bash
ffmpeg -f rawvideo -pixel_format nv21 -video_size 1280x720 -i frame.nv21 -frames:v 1 frame.png
~~~
7. 此包没有远程桌面、HTTP/MJPEG/RTSP 转发服务，需另外开发编码与传输。

推荐接续顺序：新电脑重编译 → 同一镜像复现 80 档 → 亮场/运动目标验证 → 再做 VIO 或 >100 研究。
