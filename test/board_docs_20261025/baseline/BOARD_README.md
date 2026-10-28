# GC4653 record80 板端使用说明

部署位置：`/code/camera/modules/record80/README.md`。
以下命令在荔枝派 SSH 终端执行，不是在笔记本 PowerShell 中执行。

## 1. 启动摄像头

```sh
sh /code/camera/modules/record80/run_board.sh
```

该命令会读取 YAML 参数并启动摄像头。默认前台运行，保留这个终端；需要停止时按 `Ctrl+C`，等待 `CLEANUP_DONE` 后再启动或关机。

不要直接运行底层 `camera_36record`，否则会绕过启动脚本的配置加载和安全监督。不要同时运行多个摄像头程序，也不要直接强杀或手动删除占用锁。

## 2. 检查参数（不会启动摄像头）

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
```

返回 `CONFIG_OK` 只表示配置通过校验，**不表示摄像头已启动，也不表示参数已经应用到硬件**。要运行仍需执行第 1 节命令。

## 3. 修改曝光、增益和运行时长

```sh
vi /code/camera/modules/record80/config/record80.yaml
```

修改后保存，执行参数检查，再正常停止旧进程并重新启动；不支持运行中自动热更新。

手动模式示例（只修改文件中已有的对应字段，不要重复添加同名键）：

```yaml
exposure_mode: manual
manual_exposure_us: 5000
manual_analog_gain_x1024: 1024
manual_digital_gain_x1024: 1024
manual_isp_gain_x1024: 1024
max_run_sec: 300
auto_record: false
```

这里的值仅作示例，实际以当前 YAML 为准。曝光单位为微秒，增益 1024 表示 1 倍。当前脚本允许运行时长 20～300 秒，并保留温度、MIPI、时钟恢复等保护；不是无限运行。

YAML 采用当前程序支持的平铺 `key: value` 子集，不使用嵌套、引号或行尾注释；说明注释放在单独一行并以 `#` 开头。

如果使用暗场 BLC 调整，`--check-config` 可检查 BLC 配置；运行时的 `RECORD80_BLC_VERIFY ... match=1` 用于确认实际偏移与配置一致。该验证不代表所有场景的偏色都已消除。

## 4. 预览与录像

USB 网络预览地址（程序运行期间）：

```text
http://10.133.124.1:8081/
```

`auto_record: false` 时，通过网页“开始录像”“停止录像”按钮控制；`auto_record: true` 时启动后自动录像。

板端录像位置：

```text
/code/camera/recordings/
```

采集约 80FPS，录像从编码帧中每两帧取一帧，MJPEG AVI 标称 40FPS，实际帧率以测量为准；不是全 80FPS 录像。

使用 Wi-Fi 后，SSH 应连接无线 IP。网页是否能通过无线 IP 访问，还取决于程序的监听地址和网络可达性，不能只替换 IP 就认定一定可用。

## 5. 常见问题

- **只看到 CONFIG_OK 就退出**：运行的是 `--check-config` 检查命令，请执行第 1 节启动命令。
- **几十秒后自动退出**：检查 YAML 的 `max_run_sec`，以及是否使用了临时 `MAX_RUN_SEC` 环境变量覆盖；查看退出原因是否为时间或温度限制，不要直接取消保护。
- **Camera is busy**：先检查是否已有摄像头程序运行或正在清理；不要直接删除锁或启动第二个进程。
- **修改参数没效果**：确认编辑的是本说明第 3 节的板端路径，保存后重新启动，核对启动日志。`CONFIG_OK` 本身不是硬件生效证据。
- **正常停止**：在启动终端按 `Ctrl+C`，等待清理完成；不要用直接断电代替停止录像。

本文件由笔记本项目 `modules/record80/docs/BOARD_README.md` 随部署同步，不包含 Wi-Fi 密码或其他凭据。
