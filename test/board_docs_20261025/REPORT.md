# 板端操作手册补全与文档独立同步

## 已确认的问题及处理

用户在 `/code/camera` 查看 README，把它当作当前程序使用手册。板端根 README 实为 2026-10-07 的旧实验说明；`/code/camera/modules/record80/README.md` 不存在。此前仅在本地增加模块文档且全量部署未同步根 README，不能满足实际操作需求。

本次将根/模块 README 同步为同一份当前操作手册，首页明确 YAML、曝光单位、启动及停止，之后分别说明 USB/Wi-Fi/端口转发、调参步骤、实际曝光日志、录像路径和故障排查。旧实验说明备份保留，不删除资料，不把旧实验入口继续当作当前默认用法。

## 当前参数事实

板端 `--check-config`：manual、manual_exp_us=5000、三种AE增益1024、run_sec=300、auto_record=0、Q85、手动BLC四通道256。

最近一次 session_1792942207_2568 日志稳定阶段读取到 exp_us=5000、三种增益1024。检查时没有 camera_36record 进程，所以只能描述“配置及最近运行值”，不能描述相机此刻正在曝光。

另发现该次旧运行日志尾部有大量 NUL 字节，末尾未见正常 stopped 信息。原因未知，不能推断一定是断电、SD卡或本任务修改造成；本次未运行相机、未修改或修复该日志。

## 文件范围

本地修改：

- `modules/record80/docs/BOARD_README.md`：扩充为完整操作手册，作为根/模块板端 README 的共同来源。
- `modules/record80/README.md`：增加操作手册及文档独立同步入口。根目录原有本地 README.md 修改未触碰。

本地新增：

- `modules/record80/scripts/sync_board_docs.ps1`：只上传4份文档，上传前检查文件/旧文档哈希/符号链接，暂存校验、备份、同步和安装校验；检查程序、启动脚本与YAML哈希未变。
- 本任务目录：3份基线备份（本地旧板端手册、本地模块README、下载的板端旧根README）、`sync.log` 和本报告。

板端更新/新增：

- `/code/camera/README.md`：更新旧实验说明为当前手册，旧内容已备份。
- `/code/camera/modules/record80/README.md`：新增同一份手册。
- `/code/camera/modules/record80/docs/CONFIG.md`：同步现有本地调参说明。
- `/code/camera/docs/WIFI_CONNECTION.md`：同步现有本地Wi-Fi指南。

无删除、移动、配置/程序修改、编译、录像、摄像头启动或Git写操作。未修改公共接口、类名、函数名、目录结构、配置格式或程序运行方式；新增文档同步入口不替代原部署入口。对采集性能、内存、线程和实时性无代码影响，因为运行程序字节未变化。新同步脚本只在现有 Windows PowerShell/SSH/SCP 工具链下验证，未声称 Linux/ARM64 主机执行该 PowerShell 脚本已通过。

## 真实执行和失败记录

只读：`git status --short`、读取本地 README/CONFIG/启动及部署脚本、查找 AGENTS.md、SSH 读取板端文档/进程/配置检查/日志/文件哈希。

实际操作：

1. New-Item / Copy-Item 创建本任务基线；scp 下载原根 README。
2. 编辑手册及模块说明，新增同步脚本；手册UTF-8严格解码、代码围栏成对及关键内容检查通过。
3. 首次 apply_patch 将同一路径同时作为删除和新增目标，工具拒绝该补丁，没有执行文件删除；改用直接写入已备份的文档，再作小范围补丁。
4. 新脚本首次运行因 PowerShell 数组中 HostKeyAlias 参数拼接错误，SSH 提示 `no argument after keyword hostkeyalias`，在远程只读检查前失败，没有更新板端文件。修正为独立括号表达式后重试成功。
5. 执行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File modules/record80/scripts/sync_board_docs.ps1 -BoardIp 192.168.1.102 -HostKeyAlias 10.133.125.1`，DOC_SYNC_PASS；没有全量部署。
6. SSH 读取新版根 README 首页，检查4份文档存在且SHA-256匹配；重新执行配置检查与保护文件哈希校验；PowerShell AST语法复查和基线差异空白检查通过。

## 结果与验收

- 根/模块 README 相同 SHA-256：`cdfe3b458393ca1d8283f9f4a2b3828e61a2dc4ebb28e4bfc93ada695e8d8829`。
- 调参说明哈希：`9379ad5f2dd65bf6923c5dff9d7ede8857cee2f8b16787e8c6a7971fee22d5af`。
- Wi-Fi指南哈希：`2cc0124f95b1cb12db060ac6da9edd1ccd464de1062b968dc9621745954fd604`。
- 二进制仍为 `19edda678e7fb94f7e5cbe9a943949b936e6609d455aaa9451d65e8751671725`，启动脚本仍为 `50e61201e6dd2a2e160dcfaca8d9887ca5b65ae6ebd6d27ca866affb28f6243a`，YAML仍为 `68c2efff9f061516d1acfc9c7ddccda888e6e0b79e41e40fdc9330007a916e04`。
- 静态检查、真实文档同步/回读和配置检查通过。没有执行编译、采集/录像功能、性能或全部手册步骤的重新回归；色彩问题未解决，新脚本异常回滚分支和其他网络环境未全面测试。
- 实际范围与计划一致，补丁及参数拼接失败已修正并如实记录。部署策略采用文档独立同步，避免全量部署覆盖用户板端调参。

用户验收命令：

```sh
cat /code/camera/README.md
cat /code/camera/modules/record80/README.md
sh /code/camera/modules/record80/run_board.sh --check-config
```

首页应出现完整YAML路径、曝光5000微秒的更新时快照以及启动/停止方式。该参数表随用户后续编辑可能过时，实际配置以检查输出为准。

## 备份和回退

板端备份：`/code/camera/backup_docs_20261025_233923_04b9beaa`。暂存：`/code/camera/.docs_stage_20261025_233923_04b9beaa`。它们保留未清理。

原来存在的文档按 root_README.md / module_README.md / CONFIG.md / WIFI_CONNECTION.md 名字备份；原来不存在的目标以对应 `.absent` 标记记录，不伪造旧内容。

仅恢复旧根说明可执行：

```sh
cp -p /code/camera/backup_docs_20261025_233923_04b9beaa/root_README.md /code/camera/README.md
```

其余目标仅在备份文件确实存在且确认没有后续文档修改时逐一恢复；原本不存在的新文档可以保留，不要求为回退而删除。程序、YAML、录像数据无须恢复。本地按 baseline 恢复两个对应文档，新增脚本与任务资料独立保留；不使用Git全量恢复覆盖其他工作。实际没有执行回退。
