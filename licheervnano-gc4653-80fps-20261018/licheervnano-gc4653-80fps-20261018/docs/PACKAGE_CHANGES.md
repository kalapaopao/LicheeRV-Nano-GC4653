# 本包改动、影响与回退
原 WSL camera 工程保持原样，变更只在 handoff-20261018/workspace/camera 副本：
- 新 README、HANDOVER、EXPERIMENTS_100FPS、REFERENCE_INDEX、本文件。
- 原 docs/README/RESULTS/SOURCES/哈希留作历史，迁移以根 README 和 HANDOVER 为准。
- scripts/benchmark.sh 只增80-empty映射，30/60/80等原分支不改。
- 新 build-empty.sh：提取原实验脚本的空跑构建段；新 tools/check-results.py：离线报告检查。
- 不带陈旧 docs/build-host.sh：它是根编译脚本的重复副本，从 docs 执行相对路径错误，统一用根 build.sh。
- 不带原 host_tools：依赖旧电脑路径和外部登录模块。使用常规ssh/scp，不存凭据。
- 不带旧 .o、PID/锁、缓存、Git数据、NV21/抓拍；报告 JSON/CSV/日志保留。
- SDK裁剪，保留原工具链和编译头文件层级；不是完整BSP。
- bin 在迁移副本重新编译，验证记录位于包外层 verification/。
- 小运行包只带正常/基线/AE诊断/空跑4个程序、主源码及空跑源码、脚本、配置参考和文档。
- install-board.sh 只在 /code/camera 不存在时安装，已有目录拒绝覆盖；不会自动启动或改系统文件。
- 本次不修改摄像头算法、配置格式、系统接口或原工程启动方式。主机编译仅支持随包工具链的x86_64 Linux，目标仍是原板riscv64 musl。
回退：保留原工程，弃用迁移副本即可。此次未触碰板子；以后安装的目录回退见 HANDOVER。
