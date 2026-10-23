# 源码来源与构建说明
- 原驱动及 common：官方 LicheeRV-Nano-Build 当前本地工作副本。
  https://github.com/sipeed/LicheeRV-Nano-Build/tree/main/middleware/v2
- 高速驱动四个源文件来自 MaixCDK main 的当前源码，2026-10-07 获取：
  https://github.com/sipeed/MaixCDK/tree/main/components/3rd_party/sophgo-middleware/sophgo-middleware/v2/component/isp/sensor/sg200x/gcore_gc4653
- 官方模式说明：
  https://github.com/sipeed/MaixPy/blob/main/docs/doc/zh/vision/camera.md
- 各源文件的 SHA256 在 source-sha256.txt。
- src/sensor 为下载副本；src/sensor_ae_fix 只修改 cmos_get_ae_default，让 AE 参数按当前模式索引。
- 相应修改可用 diff -u src/sensor/gc4653_cmos.c src/sensor_ae_fix/gc4653_cmos.c 查看。
- 本次不存在 Git 仓库历史读取、提交或推送操作。
- build.sh 在 WSL camera 根目录，使用同级官方 SDK headers 和工具链，并链接从当前板端只读复制的 CVI .so。
- Docker Linux engine 仍不可连接，此次不把 Dockerfile 已有等同于容器构建已完成。
- host_tools 仅部署/获取记录时使用。板端采集与测试没有 SSH、Paramiko 或电脑端程序依赖。
