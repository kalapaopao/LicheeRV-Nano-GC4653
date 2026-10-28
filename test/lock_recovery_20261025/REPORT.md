# CAMERA_LOCK_BUSY 单次安全恢复

## 原因与证据

启动脚本在接触相机前发现持久目录 `/code/camera/run/lock` 存在，直接返回 CAMERA_LOCK_BUSY。检查时该目录为空、record_cam.pid 中的2638已不存在；完整进程列表没有相机进程或监督程序，8081/8082无监听，VI无启用设备/通道，MIPI无配置设备，时钟寄存器为原值0x00200001。

板子 uptime 约14分钟，旧锁及PID文件仍在持久文件系统内；高概率是之前没有正常清理便中断/重启，残留目录跨重启保留。不能确认上次到底是断电、强制重启还是其他异常。已有锁的存在不等于摄像头此刻仍被占用。曝光8000us不是本次锁检查失败的原因。

## 执行

先读取当前脚本的互斥/退出逻辑及板端状态，再制定仅清理失效空锁的方案。没有改为“每次启动自动删除锁”，避免误删真实占用。

新增一次性脚本 `recover_empty_lock.sh`，重新核对已知相机进程、固定旧PID未变化且已不存在、锁不是符号链接、VI未启用、时钟恢复；保存检查记录后，执行精确命令 `rmdir /code/camera/run/lock`。该命令仅能移除空目录，不递归删除，目录内若新增内容会失败。

该脚本固定了本次旧PID和报告路径，不是可以反复执行的通用解锁工具。未终止任何进程，未修改或删除原record_cam.pid；正式启动随后正常重写自己的PID文件。

实际命令：

- 只读：无线SSH的ls/ps/netstat、读取锁/PID/VI/MIPI/uptime、sha256sum、配置检查；本地读取run_board.sh、rg搜索锁实现。
- New-Item创建本地任务目录，新增单次脚本。
- scp上传至 `/tmp/record80_recover_empty_lock_20261025.sh`；sh -n通过后执行，结果 STALE_EMPTY_LOCK_REMOVED，保护文件校验通过。
- `MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 RECORD_AUTOSTART=0 sh /code/camera/modules/record80/run_board.sh`，保持当前8000us参数，仅临时覆盖时限和禁用自动录像。
- scp下载最终capture.log，最终读取锁、相机进程、配置和保护文件校验。

## 验证

- 恢复后正式入口启动成功，输出LIVE_READY。
- YAML仍为手动8000us、三种增益1024、300秒、auto_record=0、BLC四通道256。实际稳定曝光7999us，这是传感器量化后的读数。
- 稳定窗口pts_fps约80.005，最终frames=1917、encoded=1908、errors=0、tuning_failed=0。
- 监督退出码0，timer_limit，CLEANUP_DONE，最高监督温度59.828°C。
- 最终MMIO=0x00200001、CCF=37125000、MIPI=0 0 0 0 0、LOCK_FREE、CAMERA_STOPPED。
- 仍有既有 `vi_sdk_get_chn_frame ... Operation not permitted` 退出警告，已保留，不能以此声称所有警告已解决。
- 程序、启动脚本、YAML在恢复前后哈希一致；没有编译、录像、色彩校准、网页/接口/性能的全面回归，也没有验证以后异常断电是否再次留锁。

## 文件与产物

- 本地新增：一次性恢复脚本、recovery.log、supervisor.log、capture.log、本报告，均在本目录。
- 板端新增：上述/tmp脚本，以及 `/code/camera/diagnostics/lock_recovery_20261025/` 中的原锁列表、PID备份、进程、VI/MIPI/uptime记录和protected.sha256。
- 板端短测新增session：`/code/camera/modules/record80/record_report/session_1792943239_1096/`，含诊断样本、日志和参数快照，没有AVI。
- 只删除了已确认失效的空锁目录，没有删除任何文件，没有移动文件，没有修改源代码、配置格式、公共接口或程序/数据格式，没有Git写操作。运行PID文件及诊断产物按正式启动原行为更新。

## 后续操作与回退

现在用户可直接重新执行原启动命令。正常停止需等待CLEANUP_DONE，再关机/更换供电。以后看到锁忙先核对占用者，不直接删锁。本次是单次恢复，没有实现自动跨重启锁回收。

没有需要恢复的程序或参数。原空锁没有业务内容；若为复现旧失败状态而重新创建 `/code/camera/run/lock` 会再次阻塞启动，不应作为正常回退步骤。证据与旧PID已留存，原运行文件和录像未删除。实际未恢复失效锁，未执行产物清理。

验收：执行 `sh /code/camera/modules/record80/run_board.sh`，应进入LIVE_READY而不是CAMERA_LOCK_BUSY；持续运行仍受300秒和温度保护。若失败，保留终端输出及新的session日志，勿用强杀、递归删除或取消安全保护替代诊断。
