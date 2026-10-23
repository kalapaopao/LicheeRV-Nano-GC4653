# 迁移包入口
将整个目录复制到新电脑即可。优先阅读 docs/HANDOVER.md。

- workspace.tar.gz：完整可重编译工程、官方工具链、最小SDK、所有实测日志与研究归档；在x86_64 Linux/WSL内解压，避免Windows解压器损坏链接。
- board-runtime.tar.gz：只用于板端的可运行小包，不含主机编译器；含主源码与空跑源码供阅读。
- install-board.sh：在板端安装小包，发现/code/camera已存在会拒绝覆盖。
- docs/：可不解压工作区就先阅读的交接文档。
- verification/：本次重编译、哈希比对与压缩包验证结果。
- SHA256SUMS：迁移文件完整性校验。

已保存的历史结果：720P/80档，60秒82.3335FPS；空跑20秒82.4994FPS。>100未跑通，画质未验收。
本次只做本地打包与构建，没有重新运行板端采集；原电脑工程与板端不改动。

## 新电脑快速构建
~~~bash
mkdir -p ~/projects/LicheeRV
cd ~/projects/LicheeRV
tar -xzf /实际位置/workspace.tar.gz
cd workspace
sha256sum -c MANIFEST.sha256
cd camera
bash build.sh
bash build-empty.sh
~~~
主机x86_64 Ubuntu22.04/WSL2，camera与SDK保持同级。详见docs/HANDOVER.md。

## 同一原板直接用
~~~sh
cd /code/camera
sh scripts/benchmark.sh 80 60
~~~
旧板端脚本未必支持新增80-empty入口；新入口随本运行包交付。
原板已有工程时无需因换电脑重新刷机。新板仍需要匹配的CVI/ISP系统镜像与GC4653配置。
