# 摄像头退出后网页无限重试修复

## 问题与结论

摄像头退出会关闭 8081/8082，SSH 登录与本地端口转发可以继续运行。旧网页使用 `setInterval(refresh,1000)`，每秒访问一次已经关闭的录像控制服务，使 SSH 持续输出 `channel ... open failed: connect failed: Connection refused`。此消息本身是端口转发的正常错误反馈，不代表摄像头仍在运行；需要修复的是网页缺少断线生命周期管理。

修复前通过无线 SSH 确认：摄像头未运行、共享锁空闲，8081/8082 无监听。未修改 sshd、VPN 或防火墙，也没有屏蔽 SSH 日志。

## 文件范围与行为

修改：

- `modules/record80/src/camera_36record.cpp`：只修改内嵌 HTML/JavaScript，增加离线状态、手动重连按钮、3 秒请求超时、失败后停止轮询/移除视频元素、页面关闭时取消请求，以及避免状态轮询重叠。
- `modules/record80/bin/camera_36record`：由现有 WSL 工具链重新构建，部署到同名板端程序。
- `modules/record80/docs/USER_GUIDE.md`：解释 SSH 转发报错、旧标签页升级和手动重连方式。

新增：本目录的 `test_page.cjs`、`install_candidate.sh`、本报告，以及基线备份、测试日志、板端返回的网页副本。

无删除、移动、Git 写操作。没有修改启动脚本、YAML、曝光、增益、BLC、白平衡、采集/录像逻辑、API 路由、监听端口和时钟/温度保护。新版网页需要 AbortController，未验证老旧浏览器。前端断线不会自动结束板端录像。

## 备份和部署

- 本地修改前备份：`baseline/camera_36record.cpp`、`baseline/camera_36record`、`baseline/USER_GUIDE.md`。
- 原程序 SHA-256：`eb88aceb0275cdfa0714a28707ba1c82f5baaa6e63598fa1a49d4ea058e95b53`。
- 新程序 SHA-256：`19edda678e7fb94f7e5cbe9a943949b936e6609d455aaa9451d65e8751671725`。
- 板端备份：`/code/camera/modules/record80/backup_preview_disconnect_20261025_232219/camera_36record`。
- 板端暂存：`/code/camera/modules/record80/.preview_disconnect_20261025_232219/`。
- 仅安装新二进制。安装前验证摄像头空闲、原程序匹配已知哈希、候选程序哈希正确，并备份原程序；未运行全量 deploy.ps1，避免覆盖用户 YAML。
- 安装前后及最终审计均验证 YAML 和启动脚本 SHA-256 不变。板端新增备份中的 `unchanged.sha256` 仅保存这两项校验值。

## 执行命令

只读查阅：`git status --short`、`Get-Content` 阅读正式源文件和构建脚本、`node --version`、无线 SSH 下的 `ps` / `netstat` / `sha256sum` / 配置检查。通过 `git diff --no-index` 比较当前文件与本任务基线；该差异命令返回 1 仅表示有差异，没有读取 Git 历史。

实际操作：

1. `New-Item`、`Copy-Item` 创建独立测试目录和三份本地基线备份。
2. `node test/preview_disconnect_20261025/test_page.cjs`：直接测试源码内嵌脚本。
3. `wsl.exe -- bash -lc 'bash /mnt/d/study/LicheeRV/modules/record80/scripts/build.sh'`：使用现有 build 目录和 SDK 构建，无新增依赖。
4. SSH 创建独立暂存目录，`scp.exe -q -O` 上传程序和安装脚本，板端执行 `sh -n` 及 `sh install_candidate.sh`，只替换二进制。
5. `MAX_RUN_SEC=20 RECORD_TEST_AUTOSTART=0 RECORD_AUTOSTART=0 sh /code/camera/modules/record80/run_board.sh`：正式入口短测。限时仅用环境变量覆盖，YAML 仍为 300 秒。
6. SSH 内使用 `curl -fsS --max-time 4 http://10.133.124.1:8081/` 获取真正部署程序的网页，另读 `http://10.133.124.1:8082/status`。未启动浏览器视频流，未发送录像 POST。
7. `node test/preview_disconnect_20261025/test_page.cjs test/preview_disconnect_20261025/board_page.html`：对板端返回的实际页面重复执行 12 项测试。
8. 下载最终 capture.log，读取最终摄像头、锁、寄存器、CCF 和文件校验状态，并对源文件/说明执行基线差异空白检查。

## 验证结果

- 编译：成功，`BUILD_RESULT=SUCCESS`。WSL 输出既有 `.wslconfig` 配置警告和无法转换 `F:\yolo\miniconda3` 路径的警告；未擅自修改全局环境。
- 脚本逻辑：源码页面及板端实际页面均 12/12 通过。覆盖健康轮询、连接拒绝、正常后断开、HTTP 错误、无效 JSON、3 秒超时、慢请求不重叠、视频错误中断请求、pagehide、录像控制成功/失败及显式手动重连。测试为 Node vm + DOM/fetch/timer 模拟，不是实际 Edge 图形界面测试。
- HTTP 接口：运行中成功取到新版页面，包含断线提示且没有旧无限轮询；8082/status 返回有效 JSON，requested=false、recording=false、write_errors=0。
- 板端运行：session 为 `session_1792941801_1731`；稳定 PTS 窗口约 80FPS，最终 frames=1934、encoded=1926、errors=0、tuning_failed=0。未录像、未对新 AVI 文件回归，也未验证网页按钮的真实写盘路径。
- 监督退出：退出码 0、timer_limit、CLEANUP_DONE；最高监督温度 66.470°C。MIPI 起始及最终为 `1 0 0 0 0`，未增长，不是全零。
- 日志仍有既有 `vi_sdk_get_chn_frame ... Operation not permitted` 退出警告，不能隐藏；监督正常结束与该警告分别记录。
- 最终状态：CAMERA_STOPPED、LOCK_FREE、MMIO=0x00200001、CCF=37125000；YAML 与启动脚本校验通过。
- 尚未验证：用户实际 Edge 浏览器经过 SSH 隧道时的断流事件细节、全部浏览器兼容性、端到端延迟、色彩校准。没有声称已经完成这些验证。

## 产物

本地：基线三文件、测试脚本、安装脚本、报告、`page_tests.log`、`board_page.html`、`board_supervisor.log`、`board_capture.log`；现有 `modules/record80/build/` 编译对象和 `bin/camera_36record` 更新。

板端：独立暂存、程序备份、校验记录及一次短测 session 诊断图片/RAW/日志，没有 AVI 录像。未清理或删除旧资料。

## 用户验收

1. 关闭所有升级前的旧预览标签页；旧页面不会自动换成新脚本。
2. 通过笔记本上的 SSH 端口转发登录，再运行原启动命令。
3. 打开 `http://127.0.0.1:8081/`，仅保留一个预览标签页。
4. 在启动终端正常 Ctrl+C，等待 CLEANUP_DONE。网页应提示连接断开、禁用录像按钮、显示“重新连接”，而不是每秒无限请求。
5. 断线瞬间已有请求或浏览器内部处理可能仍产生少量 SSH 提示；其他旧标签页、扩展或外部程序继续请求，不在这份网页脚本的控制范围内。
6. 重新启动摄像头后，手动点击“重新连接”恢复。不要在服务尚未启动时反复刷新页面，否则每次点击仍会触发实际连接失败。

## 回退

板端确认摄像头已正常停止、共享锁释放后，仅恢复本任务备份的二进制：

```sh
cp -p /code/camera/modules/record80/backup_preview_disconnect_20261025_232219/camera_36record /code/camera/modules/record80/camera_36record
sha256sum /code/camera/modules/record80/camera_36record
```

预期原哈希为上文 eb88...。不需要恢复 YAML、启动脚本或录像数据。本地按 `baseline` 中三份原文件分别恢复对应源文件、二进制和使用手册；恢复前仍需检查是否有后续修改，不能覆盖用户新增工作。本任务资料独立保留，不执行清理。实际未执行回退。
