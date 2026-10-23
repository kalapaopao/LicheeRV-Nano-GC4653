# 打包与验证报告（2026-10-18）
## 完成范围
从原 WSL camera 当前文件创建独立迁移副本，保留主源码、空跑源码、驱动、实验参考、日志与配置参考。
包含官方工具链及所需 SDK 子集，生成完整工作区与板端小运行包。
没有修改原工程，没有连接/改动板端，没有 Git 操作，没有安装依赖。

## 副本变更
新根 README、HANDOVER、EXPERIMENTS_100FPS、REFERENCE_INDEX、PACKAGE_CHANGES；
新增 build-empty.sh、tools/check-results.py；benchmark.sh 仅新增80-empty映射。
副本不带过时 docs/build-host.sh、旧路径部署助手、旧构建对象、运行锁、原始图像；无文件在原工程中删除/移动。
详见 docs/PACKAGE_CHANGES.md。构建方式仍为同级SDK，目标ABI、配置格式及摄像头代码不变。

## 已完成验证
- SDK工具链86个符号链接均指向包内且目标存在。
- sh -n / bash -n：运行脚本与3个构建脚本语法通过。
- bash build.sh / bash build-empty.sh / bash experiments/over100/build.sh：全部9个二进制编译链接成功。
- 9个重编译文件与原对应二进制 SHA256 完全相同，见 rebuilt-vs-original.json。
- 原06长测、13空跑、03基线JSON通过离线校验；原14零帧/8超时被正确拒绝。
- RISC-V ELF/musl解释器检查记录在 build-and-check.log。
- 压缩包生成后另做解压、逐文件哈希、解压路径重新编译检查，结果见 archive-verification.log。

## 命令与失败记录
只读：目录/容量/源文件/文档/日志检查，grep/sed/find/du/file/sha256sum，工具链版本。
一次 WSL rg 检索因 rg 未安装失败，已改用 grep/sed；未影响构建。未安装rg。
实际：复制到独立handoff目录、写交接文档与包内辅助脚本、执行上述3个构建、离线JSON检查、tar打包/解压、哈希校验、ZIP封装。
零帧负向检查返回1是预期拒绝，不是成功采集。
没有执行安装器到真实 /code/camera，没有执行板端摄像头测试、单元测试或网络接口测试。

## 结果边界与影响
编译通过；本地打包/离线结果检查通过。历史性能为2026-10-07原板实测，此次未重测。
80档长测82.3335FPS，空跑20秒82.4994FPS；未实现>100FPS。
画质、有效曝光、长期温升、网页转发未验证。Docker构建此前未成功连接引擎，本包交付WSL原生工具链。
CPU数值指同进程CPU时间，PTS递增不证明光学内容独立。
目标仍为原SG2002/riscv64 musl，不扩大到ARM64/Windows原生运行或其他镜像。
原目录保留，可独立弃用本迁移副本；后续板端安装/回退见HANDOVER。

## 验收
先校验外层SHA256SUMS，再在Linux解压workspace.tar.gz，进入workspace执行sha256sum -c MANIFEST.sha256。
按README重编译；原板已有目录可直接SSH运行80档。新目录安装器拒绝覆盖已存在的/code/camera。
