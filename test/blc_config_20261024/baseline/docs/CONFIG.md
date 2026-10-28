# record80 调参与启动

只维护 `config/record80.yaml` 这一份运行参数。Windows 编辑后运行 `scripts/deploy.ps1` 上传；也可直接编辑板端 `/code/camera/modules/record80/config/record80.yaml`。每次启动前执行：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
sh /code/camera/modules/record80/run_board.sh
```

`run_board.sh` 先解析并校验配置，再检查摄像头、温度及硬件时钟。配置在启动时读取一次，运行中编辑不会生效；重启前先在原终端按 `Ctrl+C`，等时钟恢复和锁释放。每次会在 `record_report/session_*/record80.yaml` 保存本次参数快照。

## 格式与参数

这是**受限的 YAML 标量子集**，用板端 `/bin/sh` 解析，避免安装 YAML 运行库：仅顶层 `key: value`；不支持缩进、列表、引号、行尾注释或重复键。独占一行的 `#` 注释可用。所有键必填，未知键报错；不要把它误当通用 YAML 解析器。

| 参数 | 允许值 | 作用 |
|---|---|---|
| `schema_version` | `1` | 配置版本 |
| `camera_mode` | `80` | 仅保留当前约80 FPS采集模式 |
| `max_run_sec` | `20`–`300` | 监督运行时长；到时自动关停 |
| `auto_record` | `true` / `false` | 时钟切换后自动开始录像；默认 `false` |
| `jpeg_quality` | `75`–`90` | 硬件 JPEG Q 值；默认 `85` |
| `exposure_mode` | `auto` / `manual` | 自动曝光或手动固定值；默认 `auto` |
| `auto_exposure_max_us` | `0` 或 `1`–`10000` | 自动曝光时间上限；`0` 不改 ISP 原设置 |
| `auto_analog_gain_max_x1024` | `0` 或 `1024`–`16384` | 自动模拟增益上限 |
| `auto_digital_gain_max_x1024` | `0` 或 `1024`–`4096` | 自动数字增益上限 |
| `auto_isp_gain_max_x1024` | `0` 或 `1024`–`4096` | 自动 ISP 数字增益上限 |
| `manual_exposure_us` | `100`–`10000` | 手动曝光时间，微秒 |
| `manual_analog_gain_x1024` | `1024`–`16384` | 手动模拟增益 |
| `manual_digital_gain_x1024` | `1024`–`4096` | 手动数字增益 |
| `manual_isp_gain_x1024` | `1024`–`4096` | 手动 ISP 数字增益 |

增益 `1024` 表示 1 倍、`2048` 表示 2 倍。`auto` 模式忽略 `manual_*`；`manual` 模式忽略 `auto_*`。默认 `auto` 且所有自动上限为 `0`，保持原先 ISP 自动曝光，不主动调用设置接口。现有 `MAX_RUN_SEC`、`RECORD_TEST_AUTOSTART` 环境变量仍可覆盖对应两项，供旧测试命令复现；正式使用建议只改 YAML。

## 调低曝光的注意事项

可先在自动模式设 `auto_exposure_max_us: 5000`，但**限制曝光时间不等于画面一定变暗**：自动曝光会提高增益补偿。一次隔离实验中，曝光约从 27822 µs 降到 4977 µs，模拟增益升至约 5996/1024 倍，亮度指标基本不变。因此要追求更暗画面，还需结合增益上限或手动模式逐项测试，并检查画面噪声、条纹和实际 `RECORD80_AE_INFO` 日志。手动模式及增益上限尚未在正式模块上板验收，先短时测试，勿直接用于重要录像。

改 JPEG Q 值会改变码率、写盘负荷和画质；板端存储带宽有限，不能由此推断 AVI 会达到 80 FPS。摄像头 VI 约80 FPS，录像每两帧取一帧，AVI 标称40 FPS，短测实际约38.8 FPS。

## 验收与回退

先执行 `--check-config`，应输出 `CONFIG_OK`；错误会输出 `BAD_RECORD80_CONFIG` 并在接触摄像头前退出。短时实测可设 `max_run_sec: 20`、`auto_record: false`，观察 `record_report/session_*/capture.log` 中 `RECORD80_AE_BEFORE`、`RECORD80_AE_INFO`、`stopped`，以及监督终端的 `CLEANUP_DONE`、`FINAL_MMIO=0x00200001`。设置 AE 后以 `RECORD80_AE_AUTO_LIMIT` 或 `RECORD80_AE_MANUAL` 的 `rc=0x0` 确认 SDK 接受，再看 `RECORD80_AE_INFO` 的实际值，不能只看配置。

若调参失败，先停止程序并等待时钟恢复，然后将 `exposure_mode: auto`、四个 `auto_*` 上限改回 `0`、`jpeg_quality: 85`，重新校验并启动。部署脚本打印板端 `BACKUP` 目录，旧二进制、脚本及原配置（如存在）可从该目录逐个复制回原位置；**不要删除录像或实验报告来回退调参**。
