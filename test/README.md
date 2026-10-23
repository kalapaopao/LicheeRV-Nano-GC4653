# LicheeRV Nano 摄像头：隔离测试区

本目录是唯一允许新增或修改文件的位置。上层 README、speed-fry、驱动、板端现有程序均不得覆盖/删除。
2026-10-19 已通过 USB NCM 与 SSH（root 账号）完成只读检测，**未更换固件、驱动、sensor mode 或板端可执行程序**。当前详细结果见 `TIMING_STUDY.md`。

## 当前实测

当前板端运行的是旧 `camera_preview_factory 60`，1080P Q95，VI/PTS/编码实测约 65.69 FPS。`/proc/mipi-rx` 的 ECC/CRC/帧头/字数/FIFO 错误计数均为零；温度读数约 77°C。旧 80 档顶部条纹仍未解决，未验证任何新方案能在 **无条纹** 前提下超过 80 FPS。

命令：
```powershell
cd D:\study\LicheeRV\test
python probe_mjpeg.py --seconds 12 --label live-baseline-20261019
```
报告：`results/live-baseline-20261019/report.json`，另有原尺寸 first.jpg、last.jpg。
实测 1920x1080，493 帧，11.906 秒，41.324 FPS 网络接收，493 个独立 SHA256，检测到 0 个 JPEG 尺寸/段错误，JPEG 载荷约 84.36 Mb/s。这不是传感器 FPS，也不说明条纹不存在。
可打开已运行的画面：http://10.133.124.1:8081/ 。仅支持单路持续预览；测试期间请关闭浏览器中的直播标签页。

## 已有研究的事实（引用上层资料，仅作只读参考）
- 1280x720 GC4653 模式板端采集约 82.37 FPS；USB NCM 预览曾测到约 82.43 FPS。
- 80 档高频模式的顶部彩条已在 ISP 之前 Bayer RAW 中出现，且 60/80/60/80 对照复现。
- 60 档约 60 FPS 无同类顶部彩条；不能用裁剪、掩盖、插帧来宣称 80 FPS 无条纹。
- 历史 100/120 FPS 请求没有产生对应的有效采集帧率。
- 旧高频选 37.125 MHz MIPI 时钟档，60 档选 27 MHz；不能在没有 sensor/MIPI 依据的情况下盲目超频。

## 需求验收门槛
1. **画面正确**：固定场景下，完整原尺寸 JPEG、未压缩 NV21、ISP 之前 RAW 三者检查条纹；录制至少 100 张跨时间样本，并人工对照顶部区域与 60 档基线。若 RAW 有异常，不能仅以 JPEG 正常宣告通过。
2. **帧率 > 80**：板端独立用 PTS/VI 实帧测量 60 秒及更长稳定窗口；重复/倒退 PTS=0，取帧错误=0，且至少在独立接收端校验连续帧速率。JPEG 不同哈希不保证不同曝光帧；输出端 FPS 不等于板端 FPS。
3. **最高稳定 FPS**：仅在模式和寄存器有数据手册支持时，逐档提高并分别检验完整画质、热稳、内存、帧丢失。任何档位不满足画质即标记失败，不报告为可用最高 FPS。

## 后续工作（需要板端 SSH 认证）
1. **只读先行**：SSH 查询当前进程命令行、`/code/camera` 版本、使用的 sensor mode、VI/ISP 日志和温度；不要直接停止正在运行的任务。
2. 将所有新的 C++ 源码、交叉编译输出和实测数据放在本目录。使用已有 SDK 工具链时仅只读引用 `speed-fry/workspace`。
3. 若确需在板端运行新程序，必须与现有程序独立部署并可完整恢复；避免覆盖 `/code/camera/bin`、脚本、固件或已有文件。先取得当前运行服务停止/切换的许可及板端专用测试目录。
4. 逐模式收集无压缩 Bayer RAW 与 JPEG，排查 GC4653 的 PLL、曝光行长、frame length、CSI lane 速率及 sensor/receiver 同步。修改任何寄存器前留对照值和风险说明。
5. 1080P 网络吞吐调优与 720P 传感器高速档是两种不同问题，不要混淆。

## 使用隔离工具
```powershell
python probe_mjpeg.py --seconds 20 --label my-run
```
工具仅以 HTTP GET 读取现有 MJPEG，并在本目录的 results/<label> 下写 first.jpg、last.jpg、report.json。每次使用新 label，防止覆盖旧报告。条纹需要人工和 RAW 证据核查；这个工具只能校验网络帧率、JPEG 段和分辨率。

其他工具：`board_probe.py`（SSH 密钥免密只读诊断）、`fetch_factory_snapshot.py`（SSH 密钥免密 SFTP 读取已有 Factory 原始样本至本目录）、`compare_raw_stripes.py`（离线 YUV 顶部行异常对照）。密码未写入脚本/报告。当前本地详细证据在 `results/board-readonly-report.txt`、`results/factory-existing-baseline-20261019/` 与 `results/stripe-nv21-comparison.json`。

## SSH 免密登录（2026-10-19 已实机验证）
Windows 已有 `C:\Users\kalapaopao\.ssh\id_rsa` 私钥和对应公钥，本次没有新建或复制私钥。运行 `setup_ssh_key.py`，通过一次密码认证仅追加公钥到板端 `/root/.ssh/authorized_keys`（保留其它授权行），然后执行禁止密码的 `ssh -o BatchMode=yes -o PreferredAuthentications=publickey -o PasswordAuthentication=no -o IdentitiesOnly=yes -i "$HOME\.ssh\id_rsa" root@10.133.124.1 "id -un; uname -m"` 验证，输出 `root` 和 `riscv64`。之后的板端只读脚本直接使用现有私钥认证。密码仅在一次性交互认证时使用，没有硬编码。注意私钥不得上传或提交到仓库。

## RAW 彩条根因隔离（2026-10-19）
**优先阅读 `ROOT_CAUSE_2026-10-19.md`**。新开发的 `raw_isolation/` 是不带JPEG/HTTP的独立 RISC-V VI/Bayer RAW 测试版；`run_raw_isolation_retry1.py` 运行请求FPS×MCLK的四组交叉对照，所有有效数据保存在 `results/raw-isolation-20261019-retry1/`。已确定此板顶部RAW彩条与 **MCLK 37.125 MHz 高速状态** 密切关联，而不是请求FPS数字；实际是sensor内部读出/PLL还是板端MIPI电气问题尚待确证。固定曝光验证见 `results/raw-isolation-20261019-manual-retry1/`，失败的零帧/磁盘写满尝试均留档。

安全约束：实验前检查板端互斥锁、温度和进程；不要删现有锁、覆盖正式二进制或任意寄存器。板端实验临时目录已清理，仅删除本次自己创建的目录，审核见 `results/raw-isolation-tmp-cleanup.txt`；保留完整本地证据。此次实验前预览已关闭，所以实验后保持关闭状态。
