# 80 档采集与笔记本预览

## 保存位置

- `saved-80/camera_bench`：从原板下载的、已验证 80 档的原程序（不是 Windows 程序）。
- `saved-80/camera_bench.cpp`、`saved-80/benchmark.sh`：板端原源码和入口。
- `saved-80/SHA256SUMS`：保存文件的校验值。
- `camera_preview80.cpp` / `camera_preview80`：新增的独立实时预览入口。
- `build-preview80.sh`：WSL 编译入口，使用本目录下 `workspace` 中原 SDK 和驱动。
- `build-preview80/`：本次生成的对象文件。

## 开始 / 停止（在荔枝派终端）

```sh
sh /code/camera/scripts/start-preview80.sh 10.133.125.1
```

笔记本双击本目录的 `view-preview80.html`，或打开：

```text
http://10.133.125.1:8080/live.mjpg
```

停止：

```sh
sh /code/camera/scripts/stop-preview80.sh
```

查看采集速度（不是浏览器刷新速度）：

```sh
tail -10 "$(cat /code/camera/run/preview80.report)/run.log"
```

预览占用摄像头期间不要同时运行 benchmark。锁由正常退出自动释放，不要手动删除锁或 kill -9。

## 设计与限制

保留原来的传感器寄存器表和 `MAIX_SENSOR_FPS=80`。独立线程只处理最新的帧，不无限排队。笔记本预览缩小为 320×180，目标上限 15 FPS；不能把传感器档位、VI 实际取帧率和预览显示帧率混为一谈。实际结果见 `preview80-run.log` 和 `preview80-receive.json`。

使用板端原有 ffmpeg 软件 MJPEG 编码，HTTP 仅绑定 USB 地址 `10.133.125.1:8080`，未启用 Wi-Fi 监听、自启或认证。只支持一个预览客户端，测试脚本与浏览器不要同时连接。断开后程序会重新监听；重连可能需要等待数秒。USB 地址变化时需修改页面和启动参数。

双击页面后如果等待时间长，关闭其他客户端，稍等后点击“重新连接画面”。如果连接失败，查看上述 run.log；不要直接重复启动采集。

## 回退

正常停止预览即可回到原采集程序，无需恢复系统文件。停止后仍可执行：

```sh
cd /code/camera
sh scripts/benchmark.sh 80 60
```

本次新增板端文件仅为 `bin/camera_preview80`、`scripts/start-preview80.sh`、`scripts/stop-preview80.sh` 及独立报告目录。原 `camera_bench`、系统配置、系统库均不替换。没有执行 Git 操作。

## 本次实测与问题记录

最终版本开启 USB 实时预览后，板端日志记录 `host_fps=81.6507..82.2311`，对应 PTS 接近，重复 PTS 和超时均为 0。10 秒笔记本接收 140 张 JPEG、140 个不同哈希，接收帧率 13.9 FPS。这是短测，不代表长期稳定性或逐帧光学曝光的认证；未测端到端毫秒延迟。样本顶部可见局部异常条纹，尚未完成画质验收。

开发过程的失败和修正：
- 最初非缓存映射使预览拖慢采集到约 8–10 FPS；改用 SDK `CVI_SYS_MmapCache` 并失效缓存，恢复高帧取帧。
- 640×360 软件编码接收约 8.6 FPS，采集会降至约 76 FPS；保守改为 320×180 降低编码负担，得到上述最终结果。
- SDK 初始化会覆盖信号处理函数，导致早期停止测试留下 ffmpeg；初始化后重新安装处理函数，并核实正常停止后无摄像头/ffmpeg 进程、无 8080 监听。开发残留进程已按确认的 PID 正常停止。
- 初次重启测试发生 `Address in use`，一次只收到 1 帧；后续已连续接收成功。页面支持手动重连，但长期/频繁断线恢复尚未压力测试。
- 客户端结束接收时 ffmpeg 会记录 `Broken pipe` / `Connection reset by peer` / `End of file`，程序随后重新监听。这些日志不表示 VI 取帧超时。
- WSL 启动报告现有 `.wslconfig` 提示及失效的 `F:\yolo\miniconda3` PATH 项；未修改环境。构建仍实际成功。
- 一次替换旧 `run-stream.sh` 因 BOM/原文不匹配失败，随后仅重写该任务生成的旧入口；一次 SSH 命令被 PowerShell 展开了远端语法，已取消并使用正确命令重试。一次状态查询因板端 netstat 不支持参数失败，已改用支持的 `netstat -ltn`。

实际执行：网卡/PID/SDK 只读检查、SSH/Paramiko SFTP 下载原程序及上传新增入口、WSL `bash build-preview80.sh` 编译、`sh -n` / Python AST 语法检查、`board-preview80.py deploy/status/stop`、`check-preview80.py` 连续接收测试、`Start-Process view-preview80.html` 请求默认浏览器打开。最后一次启动保留运行供查看；未修改启动项或安装依赖。

新增本地文件包括本说明、预览源码/二进制/构建脚本、`board-preview80.py`、`check-preview80.py`、启停脚本、HTML 页面、`saved-80/` 备份与校验文件、`build-preview80/` 编译对象、`preview80-run.log`、`preview80-receive.json` 和首尾样本 JPEG。修改本地 `README.md` 和旧 `run-stream.sh`；没有删除或移动文件，没有修改原项目接口、驱动、目录结构和系统数据格式。仅验证本块 RISC-V 板卡；其他平台未验证。
