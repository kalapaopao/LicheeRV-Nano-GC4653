# GC4653 摄像头操作手册：启动、调参、预览与录像

当前模块：`/code/camera/modules/record80`。本手册部署到板端 `/code/camera/README.md` 和 `/code/camera/modules/record80/README.md` 两处。命令使用绝对路径，不受当前目录影响。

> **参数文件：`/code/camera/modules/record80/config/record80.yaml`。启动：`sh /code/camera/modules/record80/run_board.sh`。停止：在启动终端按 Ctrl+C，等待 CLEANUP_DONE。** 不要把根目录旧 start.sh、scripts/、experiments/ 当作当前模块入口。

## 1. 曝光是多少？YAML在哪里？

在 **荔枝派终端** 执行：

```sh
# 查看当前配置，只检查，不启动
sh /code/camera/modules/record80/run_board.sh --check-config

# 修改参数
vi /code/camera/modules/record80/config/record80.yaml
```

2026-10-25 更新手册时，已核对配置与最近运行日志：

| 项目 | 当时的值 | 含义 |
|---|---|---|
| exposure_mode | manual | 手动曝光 |
| manual_exposure_us | 5000 | 5000微秒 = 5毫秒 |
| manual_analog_gain_x1024 | 1024 | 模拟增益1倍 |
| manual_digital_gain_x1024 | 1024 | 数字增益1倍 |
| manual_isp_gain_x1024 | 1024 | ISP数字增益1倍 |
| max_run_sec | 300 | 最长运行300秒 |
| auto_record | false | 在网页手动开始录像 |
| jpeg_quality | 85 | JPEG Q85 |
| black_level_mode / 四通道值 | manual / 256 | 暗场黑电平设置，不是完整色彩校准 |

**上表是更新手册时的快照，不是永久实际值。以后以板端YAML、CONFIG_OK及本次运行日志为准。** 摄像头没有运行时，只能查看配置及上次实际读数，不存在此刻的实际曝光。

默认读取上述板端文件，**不是** `/code/camera/configs/`，也不是笔记本上的YAML。只有显式设置 `RECORD80_CONFIG` 环境变量时才使用其他配置，检查输出的 `path=` 可确认。

## 2. 命令在哪输入？

| 位置 | 典型提示符 | 执行内容 |
|---|---|---|
| 笔记本Windows PowerShell | `PS C:\Users\...>` | ssh、端口转发、scp、文档同步 |
| 登录后的荔枝派终端 | `#` | vi、run_board.sh、ip、板端日志 |
| 笔记本浏览器地址栏 | 无 | HTTP预览网址 |

**窗口标题是PowerShell，不代表仍在笔记本执行。SSH登录后看到 `#` 就在板子上。不要在板端执行笔记本的转发命令。**

## 3. USB登录、启动与预览

USB数据线连接电脑和板子。在 **笔记本PowerShell**：

```powershell
ssh root@10.133.125.1
```

登录后，在 **荔枝派终端**：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
sh /code/camera/modules/record80/run_board.sh
```

等出现 `LIVE_READY`，保持窗口和程序运行，笔记本浏览器打开：

```text
http://10.133.124.1:8081/
```

只保留一个预览标签页。`CONFIG_OK` 仅表示配置校验成功，不会启动或应用硬件参数；还需执行不带 `--check-config` 的启动命令。

## 4. Wi-Fi登录与预览：当前用SSH转发

当前程序绑定USB地址 `10.133.124.1`，没有直接监听无线IP。无线SSH成功，不代表 `http://无线IP:8081/` 可用。SSH转发兼容当前程序，提供身份认证与加密。

先在 **荔枝派终端** 查询无线IP：

```sh
ip -4 addr show wlan0
```

在 **笔记本新开的PowerShell** 执行整行；末尾 `192.168.1.102` 改成板子实际无线IP：

```powershell
ssh -o ExitOnForwardFailure=yes -o HostKeyAlias=10.133.125.1 -L 127.0.0.1:8081:10.133.124.1:8081 -L 127.0.0.1:8082:10.133.124.1:8082 root@192.168.1.102
```

这条命令同时登录并建立转发，不用先普通SSH。`HostKeyAlias` 使用此前USB登录保存的身份记录；首次连接应核实指纹，不要盲目接受主机密钥变化。DHCP无线IP可能变化。

登录后，在 **荔枝派终端**：

```sh
sh /code/camera/modules/record80/run_board.sh
```

看到 `LIVE_READY`，笔记本浏览器打开：

```text
http://127.0.0.1:8081/
```

**这里用127.0.0.1，不是无线IP，也不是旧USB地址。** 8081是网页和图像，8082是录像控制。不要直接照搬日志中面向USB的网址。

- SSH窗口保持打开；连接断开后在笔记本重新执行转发命令。
- 摄像头到时退出但SSH仍在，重新启动摄像头即可，不必重建转发。
- 普通 `ssh root@无线IP` 仅登录，不建立转发。
- 只开一个预览标签页；切换Wi-Fi见 `/code/camera/docs/WIFI_CONNECTION.md`。

## 5. 修改曝光、增益：保存后怎么生效？

先在摄像头启动终端按 `Ctrl+C`，等待 `CLEANUP_DONE`，再编辑：

```sh
vi /code/camera/modules/record80/config/record80.yaml
```

例如尝试手动曝光3000微秒，只修改已有对应字段：

```yaml
exposure_mode: manual
manual_exposure_us: 3000
```

**这是编辑示例，不表示当前已经改成3000。** 不删除其他字段，不重复添加键。曝光越短通常越暗，但不等于采集FPS自动变高。

vi操作：按 `i` 编辑；完成后按 `Esc`，输入 `:wq` 回车保存。放弃编辑用 `Esc` 后输入 `:q!`。

保存后检查并启动：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
sh /code/camera/modules/record80/run_board.sh
```

**运行中修改文件不会热更新，需正常停止后重新启动。** 不直接运行底层二进制，否则绕过配置加载与监督保护。

### 常用参数

| YAML字段 | 当前允许值 | 说明 |
|---|---|---|
| exposure_mode | auto / manual | 曝光模式，不是白平衡模式 |
| manual_exposure_us | 100～10000 | 微秒 |
| manual_analog_gain_x1024 | 1024～16384 | 模拟增益，1024=1倍，2048=2倍 |
| manual_digital_gain_x1024 | 1024～4096 | 数字增益 |
| manual_isp_gain_x1024 | 1024～4096 | ISP数字增益 |
| auto_exposure_max_us | 0～10000 | 自动曝光上限，0不改原上限 |
| auto_analog_gain_max_x1024 | 0或1024～16384 | 自动模拟增益上限 |
| auto_digital_gain_max_x1024 | 0或1024～4096 | 自动数字增益上限 |
| auto_isp_gain_max_x1024 | 0或1024～4096 | 自动ISP增益上限 |
| max_run_sec | 20～300 | 不能写0表示无限 |
| auto_record | true / false | 是否自动录像 |
| jpeg_quality | 75～90 | 影响画质、码率、写盘负荷 |
| black_level_mode | default / manual | 原ISP/PQ或手动黑电平 |
| black_level_r、black_level_gr、black_level_gb、black_level_b | 各0～4095 | 四个独立黑电平字段 |

manual模式使用manual_*，auto模式使用auto_*上限。自动模式缩短曝光后可能提高增益补偿，不能保证画面一定变暗。完整说明见 `/code/camera/modules/record80/docs/CONFIG.md`。

YAML是受限格式：仅顶层 `key: value`；不支持缩进、嵌套、列表、引号、重复键、未知键和行尾注释。注释放独立一行并以 `#` 开头。保留原必需字段，camera_mode当前只支持80，不能直接改写为60。

### 颜色和曝光不是同一个参数

三种AE增益各1倍，不代表R/G/B白平衡增益都是1倍。当前仍为自动白平衡，**YAML尚无手动白平衡字段**，不要增加white_balance等未知键。

BLC256仅是特定条件下的暗场调整，不是通用色彩标定；偏红减轻不等于蓝绿、肤色正确。不同曝光、增益、光源、温度仍需验证，当前色彩校准未完成。

## 6. 怎样确认实际曝光？

`--check-config` 查看下次启动配置；`RUN_CONFIG` 确认本次读取的参数。每次运行保存：

```text
/code/camera/modules/record80/record_report/session_*/record80.yaml
/code/camera/modules/record80/record_report/session_*/capture.log
```

在 **荔枝派终端**：

```sh
LATEST=$(ls -td /code/camera/modules/record80/record_report/session_* | head -1)
echo "$LATEST"
grep RECORD80_AE_INFO "$LATEST/capture.log" | tail -3
```

`exp_us=5000 again=1024 dgain=1024 isp_gain=1024` 表示该次实际读数为5毫秒、三种增益各1倍。曝光可能按传感器行时间量化，不能只看YAML。初始化早期可能先出现其他值，应在参数应用后查看稳定阶段。

手动BLC另看 `RECORD80_BLC_SET ... readback_match=1`、`RECORD80_BLC_VERIFY ... match=1`。最新session不一定正在运行，需结合进程、文件时间判断。

## 7. 录像和下载

- auto_record=false：网页按钮开始/停止录像，不录像也可预览。
- auto_record=true：启动并完成时钟切换后自动录像。
- 板端录像目录：`/code/camera/recordings/`，AVI及对应 `*.avi.json` 元数据，不是自动保存到电脑。
- 采集约80FPS；录像每两帧取一帧，MJPEG AVI标称40FPS；实际以测量为准，网页显示速率不等于采集速率。
- 当前预览尚未实施降帧，端到端低延迟未完成验收。

在 **笔记本PowerShell** 下载（替换实际IP、文件名）：

```powershell
scp root@192.168.1.102:/code/camera/recordings/实际文件名.avi .
```

## 8. 停止、退出、关机

1. 在摄像头启动终端按一次Ctrl+C，等CLEANUP_DONE。脚本负责恢复时钟、释放资源和锁。
2. 关闭预览标签页；不需要SSH时，在板端shell提示符下输入 `exit` 退出对应会话。
3. 换供电前，停止录像和摄像头，执行 `poweroff`，等关机完成再换线，不要直接断开正在写盘的设备。

时限最多300秒；启动温度需低于70°C，达到约74.5°C保护退出。不要删除保护、直接删除未知锁或用kill -9常规停机。临时环境变量MAX_RUN_SEC、RECORD_TEST_AUTOSTART会覆盖对应配置，日常尽量只改YAML。

## 9. 故障速查

| 现象 | 怎么处理 |
|---|---|
| vi打开空白文件 | 可能是错误路径，不要保存空文件；:q!退出，先ls -l确认本手册完整YAML路径 |
| CONFIG_OK就退出 | 是检查命令，执行不带--check-config的启动命令 |
| Camera is busy | 查看已有进程和清理状态，不直接删锁或启动第二个相机程序 |
| Wi-Fi SSH成功但无线IP网页打不开 | 程序绑定USB地址，按第4节在笔记本建立转发 |
| 网页打不开/画面停了 | 核对进程、SSH、网址、时限及温度保护，只保留一个预览标签页 |
| channel ... Connection refused | 端口已关闭但浏览器仍请求，不等于摄像头没退出；关闭旧网页 |
| 网页连接已断开 | 新版停止自动请求；确认摄像头启动后点重新连接。网页断开不等于板端录像结束 |
| 退出后仍每秒刷错 | 关闭所有旧标签页，旧页面仍执行旧脚本；板端shell下Ctrl+C不会关闭SSH转发 |
| SSH Connection closed/超时 | 检查供电、路由器新IP、网络和VPN；端口转发不能修复SSH本身不通 |
| 曝光修改无效 | 查path、模式、保存和重启，核对本次日志的实际读数 |
| 颜色不自然 | 色彩校准未完成，不随机改BLC/WB；需同场景中性参照及实际WB/CCM数据 |

## 10. 文档更新与历史资料

笔记本源文件：`modules/record80/docs/BOARD_README.md`。只更新文档，在 **笔记本PowerShell**：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\study\LicheeRV\modules\record80\scripts\sync_board_docs.ps1" -BoardIp 192.168.1.102 -HostKeyAlias 10.133.125.1
```

同步根/模块README、调参说明和Wi-Fi指南，备份旧文档并校验SHA-256，**不上传程序、启动脚本或YAML**。IP改成实际值；脚本默认USB IP为10.133.125.1。

全量deploy.ps1会上传本机YAML，可能覆盖板端调参。不要为了更新README而全量部署。历史实验保留；被替换文档备份在同步脚本打印的 `/code/camera/backup_docs_*` 中，不作为当前启动入口。
