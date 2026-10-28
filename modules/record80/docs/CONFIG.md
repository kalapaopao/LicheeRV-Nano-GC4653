# record80 调参与启动

只维护 `config/record80.yaml` 这一份运行参数。Windows 编辑后运行 `scripts/deploy.ps1` 上传；也可直接编辑板端 `/code/camera/modules/record80/config/record80.yaml`。每次启动前执行：

```sh
sh /code/camera/modules/record80/run_board.sh --check-config
sh /code/camera/modules/record80/run_board.sh
```

`run_board.sh` 先解析并校验配置，再检查摄像头、温度及硬件时钟。配置在启动时读取一次，运行中编辑不会生效；重启前先在原终端按 `Ctrl+C`，等时钟恢复和锁释放。每次会在 `record_report/session_*/record80.yaml` 保存本次参数快照。

## 格式与参数

这是**受限的 YAML 标量子集**，用板端 `/bin/sh` 解析，避免安装 YAML 运行库：仅顶层 `key: value`；不支持缩进、列表、引号、行尾注释或重复键。独占一行的 `#` 注释可用。原有键必填，未知键报错；新增黑电平字段可省略以兼容旧YAML，但选择手动黑电平时四通道值必须全部填写。不要把它误当通用 YAML 解析器。

| 参数 | 允许值 | 作用 |
|---|---|---|
| `schema_version` | `1` | 配置版本 |
| `camera_mode` | `80` | 仅保留当前约80 FPS采集模式 |
| `max_run_sec` | `20`–`300` | 监督运行时长；到时自动关停 |
| `auto_record` | `true` / `false` | 时钟切换后自动开始录像；默认 `false` |
| `jpeg_quality` | `75`–`90` | 硬件 JPEG Q 值；默认 `85` |
| `exposure_mode` | `auto` / `manual` | 自动曝光或手动固定值；当前预设为 `manual` |
| `auto_exposure_max_us` | `0` 或 `1`–`10000` | 自动曝光时间上限；`0` 不改 ISP 原设置 |
| `auto_analog_gain_max_x1024` | `0` 或 `1024`–`16384` | 自动模拟增益上限 |
| `auto_digital_gain_max_x1024` | `0` 或 `1024`–`4096` | 自动数字增益上限 |
| `auto_isp_gain_max_x1024` | `0` 或 `1024`–`4096` | 自动 ISP 数字增益上限 |
| `manual_exposure_us` | `100`–`10000` | 手动曝光时间，微秒 |
| `manual_analog_gain_x1024` | `1024`–`16384` | 手动模拟增益 |
| `manual_digital_gain_x1024` | `1024`–`4096` | 手动数字增益 |
| `manual_isp_gain_x1024` | `1024`–`4096` | 手动 ISP 数字增益 |
| `black_level_mode` | `default` / `manual` | `default`不改ISP/PQ黑电平；缺少此键时按`default`兼容旧配置 |
| `black_level_r` | `0`–`4095` | 手动R通道黑电平，SDK RAW12域数值 |
| `black_level_gr` | `0`–`4095` | 手动Gr通道黑电平 |
| `black_level_gb` | `0`–`4095` | 手动Gb通道黑电平 |
| `black_level_b` | `0`–`4095` | 手动B通道黑电平 |

增益 `1024` 表示 1 倍、`2048` 表示 2 倍。`auto`模式忽略`manual_*`；`manual`模式忽略`auto_*`。自动模式且所有自动上限为0时，不主动改ISP曝光属性。现有`MAX_RUN_SEC`、`RECORD_TEST_AUTOSTART`环境变量仍可覆盖对应两项，供旧测试命令复现；正式使用建议只改YAML。

当前配置保留用户板端设置：手动曝光5000us、三种AE增益1倍、最长300秒、不自动录像，并加入手动BLC256。以后重新部署会上传本机YAML覆盖板端参数，若只在板端改过参数，部署前应先同步或备份，不能用旧配置覆盖新调参。

## 黑电平：让正式入口使用诊断照片的设置

之前BLC256照片来自独立诊断程序，不是原正式入口，也没有后期修图。现在同一个正式启动命令会读取：

```yaml
black_level_mode: manual
black_level_r: 256
black_level_gr: 256
black_level_gb: 256
black_level_b: 256
```

启动检查会显示`black_level_mode=manual blc=256,256,256,256`。相机初始化后先设置并读回属性，日志应有`RECORD80_BLC_SET ... rc=0x0 readback_match=1`；约10秒后核对ISP内部实际offset，日志应有`RECORD80_BLC_VERIFY ... offsets=256,256,256,256 match=1`。失败会停止并报错，不会静默按旧值运行。`--check-config`只校验格式，不会设置相机。

要恢复原ISP/PQ黑电平，仅把`black_level_mode`改为`default`，保存并重启。四通道值此时不应用，旧YAML完全不含这五个字段也继续按原行为运行。它不控制白平衡；保留原自动白平衡，不保证所有背景无局部红/绿偏色。

**256只在当前5000us、1倍增益条件下完成遮光及实景短测。**曝光/增益/温度或模组变化后需重新验证暗部细节和校准范围，不能把它当作所有ISO的通用出厂标定值。这是RAW12/ISP域数值，不是JPEG的0–255亮度值。

## 调低曝光的注意事项

可先在自动模式设 `auto_exposure_max_us: 5000`，但**限制曝光时间不等于画面一定变暗**：自动曝光会提高增益补偿。一次隔离实验中，曝光约从27822us降到4977us，模拟增益升至约5996/1024倍，亮度指标基本不变。因此要追求更暗画面，还需结合增益上限或手动模式逐项测试，并检查画面噪声、条纹和实际`RECORD80_AE_INFO`日志。手动5000us/1倍增益已完成短测，但增益上限与其他组合未逐项上板验收，先短测，勿直接用于重要录像。

改 JPEG Q 值会改变码率、写盘负荷和画质；板端存储带宽有限，不能由此推断 AVI 会达到 80 FPS。摄像头 VI 约80 FPS，录像每两帧取一帧，AVI 标称40 FPS，短测实际约38.8 FPS。

## 验收与回退

先执行 `--check-config`，应输出 `CONFIG_OK`；错误会输出 `BAD_RECORD80_CONFIG` 并在接触摄像头前退出。短时实测可设 `max_run_sec: 20`、`auto_record: false`，观察 `record_report/session_*/capture.log` 中 `RECORD80_AE_BEFORE`、`RECORD80_AE_INFO`、`stopped`，以及监督终端的 `CLEANUP_DONE`、`FINAL_MMIO=0x00200001`。设置 AE 后以 `RECORD80_AE_AUTO_LIMIT` 或 `RECORD80_AE_MANUAL` 的 `rc=0x0` 确认 SDK 接受，再看 `RECORD80_AE_INFO` 的实际值，不能只看配置。

若需恢复原ISP自动行为，先停止并等待时钟恢复，然后将`black_level_mode: default`、`exposure_mode: auto`、四个`auto_*`上限改为0、`jpeg_quality: 85`，重新校验并启动。若只回退BLC，不必改变曝光。部署脚本打印板端`BACKUP`目录，旧二进制、脚本及原配置（如存在）可逐个复制回原位置；旧脚本不接受新BLC键，所以整版回退须同时恢复配套YAML。**不要删除录像或实验报告来回退调参。**
