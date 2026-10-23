# 历史启动入口逐项归档（删除前快照）

> **此文档创建于清理之前。** 仅旧的启动、停止、构建和实验运行脚本从主分支移除；历史 C/C++ 源码、测试报告、JSON 指标仍在对应目录。所有被移除脚本的完整原文仍可从 Git 只读提交 [8fe1a520](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/tree/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1) 恢复。

**清理范围：** 109 个历史调用/构建/板端辅助脚本，当前唯一推荐运行方案为 `test/clock36_live_20261023/live_36_supervisor.sh`，构建入口 `build_long.sh`。

## 文档和恢复规则

- **逐项记录**下面每个删除的路径、用途、实验类别、源码 SHA-256 和旧版 Git 永久链接；遇到旧方案故障时查历史记录，不要直接复活到当前生产启动。
- **保留 Git 历史，不做 git filter-branch / rebase / 强推**；这些脚本的内容可通过 `git show 8fe1a520:<原路径>` 取回。
- 删除脚本不代表否定历史成果：27MHz 60FPS、69.53FPS、70.69FPS 是有效阶段，37.125MHz 约82FPS因彩条失败，72FPS部分RAW实验出现CRC；更多证据见 [完整技术时间线](EXPERIMENT_DECISIONS.md)。
- 文件名称相近、不同开发阶段可能为重复实现，**记录的是文件存在与技术线索**，不虚构每份脚本都有独立稳定的现场结果。

## 历史入口全量记录

### 01 初版集成与安装（1个）

该实验组结论：旧安装/设备部署探索，非当前运行入口。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`licheervnano-gc4653-80fps-20261018/licheervnano-gc4653-80fps-20261018/install-board.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/licheervnano-gc4653-80fps-20261018/licheervnano-gc4653-80fps-20261018/install-board.sh) | 设备部署/安装 | `a1b95c192c73961ec57cae99ec1b76c6b75ac011bc3034f771b5bf7e0ba91128` |

### 02 720P 原厂/高速预览（13个）

该实验组结论：旧60/80档预览;37.125MHz达约82FPS但有RAW彩条。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`speed-fry/build-preview-hd.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/build-preview-hd.sh) | 交叉编译/重新编译 | `5d1e2173422bf810981b0a15f76df411e7faaba99cb35e21e66997c84b82c3ba` |
| [`speed-fry/build-preview-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/build-preview-main.sh) | 交叉编译/重新编译 | `70579d327cd28c071f48c0de01cfa61be07fd7a1ec303df334999c7d30e8d869` |
| [`speed-fry/build-preview80.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/build-preview80.sh) | 交叉编译/重新编译 | `25e0b6c9ecc024e502ddd9b94aaf77149150c7d9cfdf863d3ddc4054f4ffbdb1` |
| [`speed-fry/official-tests/build_factory_preview.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/build_factory_preview.sh) | 交叉编译/重新编译 | `d6b4f0e18f6b49c32c42f27c2f76406a97d5372f93e9f3e9b297fffbec972d31` |
| [`speed-fry/official-tests/run_factory.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/run_factory.py) | 实验执行/扫描/对照 | `cfc844877fdc61aad85a1ddae91c52e018274da1544affd6a493c2fea4bd5da8` |
| [`speed-fry/official-tests/run_sensor_test.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/run_sensor_test.py) | 实验执行/扫描/对照 | `ef4c964758e26795809ad34d32e26c7e0c4dd123c4958f9fe4381ef2a34ca7dc` |
| [`speed-fry/official-tests/start-preview-factory.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/start-preview-factory.sh) | 启动/重启管理 | `ea4b0878d8b97fc38af51f92fc93e38f18aee4b7897abfe508dd017dbc7d55ec` |
| [`speed-fry/official-tests/stop-preview-factory.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/stop-preview-factory.sh) | 关闭与释放资源 | `03b3a5fc838ecee1397c3820ab44cb1ff8c7c18bec7540d8e4bf1abafd2e057e` |
| [`speed-fry/run-stream.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/run-stream.sh) | 实验执行/扫描/对照 | `fb4d8bf3cafa2c7b92318b1609f49d332b3b0787638ebb28616f56565f60ac48` |
| [`speed-fry/start-preview-hd.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/start-preview-hd.sh) | 启动/重启管理 | `5150f8145d1dab1b962d82107ec557a32ccd150e921cb576b517a8c597b88823` |
| [`speed-fry/start-preview80.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/start-preview80.sh) | 启动/重启管理 | `33d29543453830196b5c638c25415b766fcc917ea136221ada0f7a4fab8cecb6` |
| [`speed-fry/stop-preview-hd.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stop-preview-hd.sh) | 关闭与释放资源 | `49c50d9264fd972717c5b4278905b5e779b7a3f32db8ae48243e8adb733d2bad` |
| [`speed-fry/stop-preview80.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stop-preview80.sh) | 关闭与释放资源 | `ff881428fdc977599c42af8d55d1c25446ba0fb28bc33e1461d82d813500b899` |

### 03 彩条根因隔离（3个）

该实验组结论：80档Bayer RAW顶行异常;关闭压缩/TNR/DPC不能消除，旧方案退役。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`speed-fry/stripe-diagnostic/run_ab.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stripe-diagnostic/run_ab.py) | 实验执行/扫描/对照 | `d670d055b2e107b7f1a59ad3388a47d8249f8346023eafc1b6315a55677058ab` |
| [`speed-fry/stripe-diagnostic/start-preview-hd.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stripe-diagnostic/start-preview-hd.sh) | 启动/重启管理 | `5150f8145d1dab1b962d82107ec557a32ccd150e921cb576b517a8c597b88823` |
| [`speed-fry/stripe-diagnostic/stop-preview-hd.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stripe-diagnostic/stop-preview-hd.sh) | 关闭与释放资源 | `49c50d9264fd972717c5b4278905b5e779b7a3f32db8ae48243e8adb733d2bad` |

### 04 原始采集、分辨率和时序试验（29个）

该实验组结论：HTS/VTS/RAW/传输隔离，结果以原始报告/JSON为准。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/build_hts.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/build_hts.sh) | 交叉编译/重新编译 | `e47fd8ccdc93781bcd597bd64648be3178fb6a3d6632f96f8280832f875a7639` |
| [`test/factory_midhts/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/factory_midhts/build.sh) | 交叉编译/重新编译 | `db8540627a765f0f2a366cb43e485265f611a74c083fd4e9bbe941e63f5fece1` |
| [`test/factory_midhts/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/factory_midhts/rebuild-sensor.sh) | 交叉编译/重新编译 | `1572fbd7caa56ac172be9a83de252eb1528858af982b9c764810371ebf51c0a7` |
| [`test/factory_timing/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/factory_timing/build.sh) | 交叉编译/重新编译 | `db8540627a765f0f2a366cb43e485265f611a74c083fd4e9bbe941e63f5fece1` |
| [`test/factory_timing/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/factory_timing/rebuild-sensor.sh) | 交叉编译/重新编译 | `1572fbd7caa56ac172be9a83de252eb1528858af982b9c764810371ebf51c0a7` |
| [`test/minraw/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw/build.sh) | 交叉编译/重新编译 | `37998b3d7c164822d2c8d9f85df51355906d4b080e942aaa0d8bf410a554f178` |
| [`test/minraw/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw/rebuild-main.sh) | 交叉编译/重新编译 | `c72214fdd136d8a90da1c26c4da9238f94fb1c4dc4f679f1c45bde68136d19bf` |
| [`test/minraw36/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw36/build.sh) | 交叉编译/重新编译 | `e55306f12aa38d32c971dada0cc07a23c5365d749b6c58878d3e3988ea8ecf79` |
| [`test/minraw_spec/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw_spec/build.sh) | 交叉编译/重新编译 | `d18ff808a23aa82ac08afa6be93a80b68a25aa5ce092a60532b24de18e5357fd` |
| [`test/minraw_spec/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw_spec/rebuild-main.sh) | 交叉编译/重新编译 | `dbc5520f0a8fadd9b86237b2a7fc3c924afcd77e41fc9900657ceb58d4178ff7` |
| [`test/minraw_vts/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw_vts/build.sh) | 交叉编译/重新编译 | `219b5874d970fcb2ca69ea7495dab5ca0220169a0f9e3c6c0adb94c0b480abf6` |
| [`test/minraw_vts/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/minraw_vts/rebuild-main.sh) | 交叉编译/重新编译 | `dfc45eb08860c32f17dbc20a28ee96763d9999c5e5a03b4af6b058ab104ad09f` |
| [`test/raw_isolation/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/raw_isolation/build.sh) | 交叉编译/重新编译 | `69ff55682908b804e1d46038cd7e5291b1ddad7f02f751acd3b9cfbc8d8a7dae` |
| [`test/raw_isolation/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/raw_isolation/rebuild-main.sh) | 交叉编译/重新编译 | `d34ac18ffe2d8bc4a55d400a27f065fd4a3eccc016158d734932680552455b6d` |
| [`test/run_1080_midhts.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_1080_midhts.py) | 实验执行/扫描/对照 | `b24e0797c5ac19c09afb1c0b8358eb30131a351d2c3de71effeed191236676da` |
| [`test/run_1080_midhts_1200_control.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_1080_midhts_1200_control.py) | 实验执行/扫描/对照 | `62aca4a9afe5a7ddd3fdf1d15d6ab936ea005efa2f7b89c704acf093d3c73e99` |
| [`test/run_1080_midhts_1200_long.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_1080_midhts_1200_long.py) | 实验执行/扫描/对照 | `3fe031e9563a4c468ca0a81384fe49f38a0bda3855993f700c2aa581d17b1c78` |
| [`test/run_hts_experiment.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_hts_experiment.py) | 实验执行/扫描/对照 | `b3b7698f54cf43c4389243c4ea1225b2f4b72491c664b39deca8df6f805b6a17` |
| [`test/run_hts_experiment_step2.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_hts_experiment_step2.py) | 实验执行/扫描/对照 | `4488c6ea57b03f743e4f3e7dbbca8278cf405d0f824fa38f732f58ec4ee71133` |
| [`test/run_hts_sweep.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_hts_sweep.py) | 实验执行/扫描/对照 | `719c2308885db560da6cc8d77d691d7864f0ae610923ccc49b31bd7a10f21966` |
| [`test/run_minraw36_baseline.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_minraw36_baseline.py) | 实验执行/扫描/对照 | `ee387b7f3342dff2fae95ceef19d907395cee57280d1fd3d8ea39e2b91848db6` |
| [`test/run_minraw_ab.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_minraw_ab.py) | 实验执行/扫描/对照 | `b8760dcb5ebb3857f888033d2cee23c12dc46f4f848d8ef2c0e2f0b6a95d74f5` |
| [`test/run_raw_isolation.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_raw_isolation.py) | 实验执行/扫描/对照 | `5861d67745d74f25f91597ce2906fb26a1ccd9a8f572b282669ec613d07750fb` |
| [`test/run_raw_isolation_manual.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_raw_isolation_manual.py) | 实验执行/扫描/对照 | `7d3a601a309993481d15ac8bdc8276265a78420dfc8310b67323283e0e84c277` |
| [`test/run_raw_isolation_manual_retry1.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_raw_isolation_manual_retry1.py) | 实验执行/扫描/对照 | `de1466159b205f6c1db0b52cbb9197f53e2df6e5261ff3ca339c01fc579afb68` |
| [`test/run_raw_isolation_retry1.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_raw_isolation_retry1.py) | 实验执行/扫描/对照 | `686e0eee4fbee1ed5c885ccff1c21b7b064048e9c61dbf70421d0e62f77bdcb5` |
| [`test/run_spec27_hts.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_spec27_hts.py) | 实验执行/扫描/对照 | `48ae4013cc45197d46afea8bf827b5ba9d068a905913db28d86e3dcfb55cefd8` |
| [`test/run_spec27_long.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_spec27_long.py) | 实验执行/扫描/对照 | `a1c4c2f53f38a2e481a03515a948b458a3a16b49e70b303c09a409668bd943db` |
| [`test/run_vts27.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/run_vts27.py) | 实验执行/扫描/对照 | `da5e5a41efc1cb3425c428baf65b6a95116d97029dcc9b4f344396bd9b924e97` |

### 05 1080P 27MHz 稳定基线（2个）

该实验组结论：保留成果:1920×1080、约69.53FPS，窗口内无MIPI增错。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/stable_69p5_1080p/source/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/stable_69p5_1080p/source/build.sh) | 交叉编译/重新编译 | `db8540627a765f0f2a366cb43e485265f611a74c083fd4e9bbe941e63f5fece1` |
| [`test/stable_69p5_1080p/source/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/stable_69p5_1080p/source/rebuild-sensor.sh) | 交叉编译/重新编译 | `1572fbd7caa56ac172be9a83de252eb1528858af982b9c764810371ebf51c0a7` |

### 06 1080P 70FPS HTS 优化（12个）

该实验组结论：保留成果:HTS1180约70.69FPS；边界HTS1190曾出现WordCount错误。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/over70_lab/candidate_70p7/source/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/candidate_70p7/source/build.sh) | 交叉编译/重新编译 | `d9cfa4bd81708525159ae016b343b3c3efe6fa8cf4f71684b25e5e1169d8ed02` |
| [`test/over70_lab/candidate_70p7/source/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/candidate_70p7/source/rebuild-main.sh) | 交叉编译/重新编译 | `05ebf402821a3c49ca7e123ab04b6a2d34a8e7d3eafbd32bfc9186760a41222d` |
| [`test/over70_lab/candidate_70p7/source/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/candidate_70p7/source/rebuild-sensor.sh) | 交叉编译/重新编译 | `45d80d803accd996e4d88882e7077e2c402ebcd50881618638a67bd7a574971e` |
| [`test/over70_lab/run_1180_long.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/run_1180_long.py) | 实验执行/扫描/对照 | `51bb0e470745425ed46e5e86291c2719b48d9c3f03e71d887daabfd0412f7a82` |
| [`test/over70_lab/run_empty_1080.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/run_empty_1080.py) | 实验执行/扫描/对照 | `65e51d4c0985fdff68676670eb39521cafa46089ec5370465eb69af958980a8f` |
| [`test/over70_lab/run_hts_sweep.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/run_hts_sweep.py) | 实验执行/扫描/对照 | `f0dc270eda1708c396ff1df2dd401d237a1e407a2fbae83b23a5e1ed5b97298e` |
| [`test/over70_lab/run_lab.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/run_lab.py) | 实验执行/扫描/对照 | `6610761241747507527f19eaf4e72976b5b3e778aa5cb925fd54f9bb42e13cbf` |
| [`test/over70_lab/run_vts_sweep.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/run_vts_sweep.py) | 实验执行/扫描/对照 | `314dc4c0de9c2c02ab7131a6445d45fd9d7f11f1926291eaffac193fd2e23613` |
| [`test/over70_lab/source/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/source/build.sh) | 交叉编译/重新编译 | `d9cfa4bd81708525159ae016b343b3c3efe6fa8cf4f71684b25e5e1169d8ed02` |
| [`test/over70_lab/source/build_empty.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/source/build_empty.sh) | 交叉编译/重新编译 | `bd3b72c2f4c5b61b5792d1c595d4c66798810809a04f8f95489397efe6809b2b` |
| [`test/over70_lab/source/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/source/rebuild-main.sh) | 交叉编译/重新编译 | `05ebf402821a3c49ca7e123ab04b6a2d34a8e7d3eafbd32bfc9186760a41222d` |
| [`test/over70_lab/source/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_lab/source/rebuild-sensor.sh) | 交叉编译/重新编译 | `45d80d803accd996e4d88882e7077e2c402ebcd50881618638a67bd7a574971e` |

### 07 1080P 72FPS / RAW探索（21个）

该实验组结论：VTS/RAW提速边界试验;带宽与MIPI报错风险。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/fps80_bayer1080/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_bayer1080/build.sh) | 交叉编译/重新编译 | `0e29c8e90fab29b13815eea1230e4a2e1895557a60ae1c42b326ae9d742648cd` |
| [`test/fps80_bayer1080/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_bayer1080/rebuild-main.sh) | 交叉编译/重新编译 | `c72214fdd136d8a90da1c26c4da9238f94fb1c4dc4f679f1c45bde68136d19bf` |
| [`test/fps80_bayer1080/run_bayer.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_bayer1080/run_bayer.py) | 实验执行/扫描/对照 | `3ae8d07f5a0e04b37b4bb5f4c743dfc39858d81817ce9e3dec7ede31d5cad392` |
| [`test/fps80_vts_trial/run_lab.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/run_lab.py) | 实验执行/扫描/对照 | `94cc9711bef24947db44e2b63b5caf2d3007cafcdf897ecd1de9a04eb57277b7` |
| [`test/fps80_vts_trial/run_vts_sweep.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/run_vts_sweep.py) | 实验执行/扫描/对照 | `0ab9f7aa7abe69598a2b2f6387a784f5b3c85d16202f7223fc9e21fa4d1af1b1` |
| [`test/fps80_vts_trial/source/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/source/build.sh) | 交叉编译/重新编译 | `d9cfa4bd81708525159ae016b343b3c3efe6fa8cf4f71684b25e5e1169d8ed02` |
| [`test/fps80_vts_trial/source/build_empty.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/source/build_empty.sh) | 交叉编译/重新编译 | `bd3b72c2f4c5b61b5792d1c595d4c66798810809a04f8f95489397efe6809b2b` |
| [`test/fps80_vts_trial/source/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/source/rebuild-main.sh) | 交叉编译/重新编译 | `05ebf402821a3c49ca7e123ab04b6a2d34a8e7d3eafbd32bfc9186760a41222d` |
| [`test/fps80_vts_trial/source/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fps80_vts_trial/source/rebuild-sensor.sh) | 交叉编译/重新编译 | `45d80d803accd996e4d88882e7077e2c402ebcd50881618638a67bd7a574971e` |
| [`test/frozen_72p18_raw1080/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/frozen_72p18_raw1080/build.sh) | 交叉编译/重新编译 | `0e29c8e90fab29b13815eea1230e4a2e1895557a60ae1c42b326ae9d742648cd` |
| [`test/over70_next/run_1165_long.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/run_1165_long.py) | 实验执行/扫描/对照 | `5582af3aa9fd1149cd46f89c9abd6b6011b2bc9f85b13d9f40cce4e2889a462f` |
| [`test/over70_next/run_1165_short.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/run_1165_short.py) | 实验执行/扫描/对照 | `e37937af4549a1ae5b7813cd4a88d24ac25608618dda57cc11c568c62341ccf1` |
| [`test/over70_next/run_1175_long.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/run_1175_long.py) | 实验执行/扫描/对照 | `9c6738345f7b6604d447bfc3ed56bf7d3e7b586689607bcb5a1f4a60112bc5ce` |
| [`test/over70_next/run_lab.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/run_lab.py) | 实验执行/扫描/对照 | `94cc9711bef24947db44e2b63b5caf2d3007cafcdf897ecd1de9a04eb57277b7` |
| [`test/over70_next/source/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/source/build.sh) | 交叉编译/重新编译 | `d9cfa4bd81708525159ae016b343b3c3efe6fa8cf4f71684b25e5e1169d8ed02` |
| [`test/over70_next/source/build_empty.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/source/build_empty.sh) | 交叉编译/重新编译 | `bd3b72c2f4c5b61b5792d1c595d4c66798810809a04f8f95489397efe6809b2b` |
| [`test/over70_next/source/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/source/rebuild-main.sh) | 交叉编译/重新编译 | `05ebf402821a3c49ca7e123ab04b6a2d34a8e7d3eafbd32bfc9186760a41222d` |
| [`test/over70_next/source/rebuild-sensor.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/over70_next/source/rebuild-sensor.sh) | 交叉编译/重新编译 | `45d80d803accd996e4d88882e7077e2c402ebcd50881618638a67bd7a574971e` |
| [`test/stable_72p18_raw1080/snapshot/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/stable_72p18_raw1080/snapshot/build.sh) | 交叉编译/重新编译 | `0e29c8e90fab29b13815eea1230e4a2e1895557a60ae1c42b326ae9d742648cd` |
| [`test/stable_72p18_raw1080/snapshot/rebuild-main.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/stable_72p18_raw1080/snapshot/rebuild-main.sh) | 交叉编译/重新编译 | `c72214fdd136d8a90da1c26c4da9238f94fb1c4dc4f679f1c45bde68136d19bf` |
| [`test/stable_72p18_raw1080/snapshot/run_bayer.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/stable_72p18_raw1080/snapshot/run_bayer.py) | 实验执行/扫描/对照 | `3ae8d07f5a0e04b37b4bb5f4c743dfc39858d81817ce9e3dec7ede31d5cad392` |

### 08 合法 36MHz 时钟/驱动探索（3个）

该实验组结论：拟编译模块与clock API；旧kernel ABI与模块不匹配，未完成正规驱动。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/clock36_safe_20261019/build_kernel.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_safe_20261019/build_kernel.sh) | 交叉编译/重新编译 | `6322a74d1b7cfd7ce256f791458559aea933ec4789aaece91965916898cec1f8` |
| [`test/clock36_safe_20261019/userland/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_safe_20261019/userland/build.sh) | 交叉编译/重新编译 | `349ff9d66a55b6be949d7b0b41640ea199db115e70ad8f05fcdfc571f3a2bd1c` |
| [`test/clock36_safe_20261019/userland/run_27_control.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_safe_20261019/userland/run_27_control.py) | 实验执行/扫描/对照 | `65e86f5556b0e08972a3e4710907e672395b32577e7c439862dfb862712f0292` |

### 09 当前方案以前的 A/B 小试（3个）

该实验组结论：分频32/33 A/B、RAW12分析，技术成果保留，临时启动器退役。

| 删除前相对路径（点击查看旧版完整源码） | 作用 | SHA-256（文件内容） |
|---|---|---|
| [`test/clock36_live_20261023/build.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_live_20261023/build.sh) | 交叉编译/重新编译 | `fe8e1b5daf6a57bd7c8473e0e5cde386a4d790e111e5123fb7977ba7d8d09f6e` |
| [`test/clock36_live_20261023/run_board_long.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_live_20261023/run_board_long.sh) | 实验执行/扫描/对照 | `1b53282b9221502d6a659785ade23cf321001d2dabb5477a208edc339a2c2c65` |
| [`test/clock36_live_20261023/run_board_test.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_live_20261023/run_board_test.sh) | 实验执行/扫描/对照 | `c722397d67feeb22507985150967e72d4571619f9f9c84f070d401b937f06b8e` |

### 10 名称未以 start/run 开头的其他旧板端调用工具（22个）

这些脚本虽没有传统 start/run 名称，但经实际源码检查，它们仍会部署/请求旧版摄像头、执行旧的板端基准、修改旧工程文件、处理旧内核构建或访问板端。为了只保留一个推荐的板端调用方案，也一起从主分支退役；原版均保留在同一个固定Git提交中。

| 删除前完整路径（打开旧版源码） | 旧用途 | SHA-256 |
|---|---|---|
| [`speed-fry/saved-80/benchmark.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/saved-80/benchmark.sh) | 旧板端摄像头启动/管理/状态检测 | `907ced1e5ea8955da316313f2a395f6147e796095126dc9825cfbaba116d11c0` |
| [`speed-fry/board-hd.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/board-hd.py) | 旧板端摄像头启动/管理/状态检测 | `3f770a2bd845f0d07c47740f929ac4f253d9c4c128b832daf308fb2f7453fe51` |
| [`speed-fry/board-preview80.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/board-preview80.py) | 旧板端摄像头启动/管理/状态检测 | `429da31c94fd8241c7a0fc8fd77d7e469cf562626160f5ab11f76022dff47dd3` |
| [`speed-fry/check-preview-hd.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/check-preview-hd.py) | 旧板端摄像头启动/管理/状态检测 | `cb724a5a6e8fcd797f597fc10ab199190fbd8ec253a59014cbde478c065da7f6` |
| [`speed-fry/check-preview80.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/check-preview80.py) | 旧板端摄像头启动/管理/状态检测 | `84fe48c44ffa54314159040af62955a61905e36610b5a3c6d5d1059e29f77b50` |
| [`speed-fry/official-tests/board_factory_preview.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/board_factory_preview.py) | 旧板端摄像头启动/管理/状态检测 | `699a9791211b3302eb3afc3fabbd219053003789bdf92a98b8cc12596b5c5324` |
| [`speed-fry/official-tests/receive.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/official-tests/receive.py) | 旧HTTP视频接收/诊断 | `952ad111610c4e21bce9c71a9905b1681d1ec88cbaa225b0007c4b0ba8289802` |
| [`speed-fry/patch_build.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/patch_build.py) | 旧时钟/源码构建或补丁辅助 | `5b472bccbed597248939e3c0a6faa9e746861055c2fc48aebd57ce16e1553254` |
| [`speed-fry/patch_stream.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/patch_stream.py) | 旧时钟/源码构建或补丁辅助 | `d782453ddd682a1231dc24c5caf937721d11477b9e89623e284c078c75bb027c` |
| [`speed-fry/stripe-diagnostic/verify_restore.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/speed-fry/stripe-diagnostic/verify_restore.py) | 旧实验部署、清理或验证 | `9a1dc09bf3db0e53862dc96ce55f25d1059ea5f79f967a5d03a39ae05552ed9d` |
| [`test/board_lock_status.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/board_lock_status.py) | 旧板端摄像头启动/管理/状态检测 | `8313ca4fc5d0f172e483f1f0539e2335fa32eefa5a45dc23e83337087c96beaf` |
| [`test/board_probe.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/board_probe.py) | 旧板端摄像头启动/管理/状态检测 | `14a778f1beab8084f3f68bf02a1fad45d38080929333b6c8e164d65f25e1c88e` |
| [`test/cleanup_own_tmp.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/cleanup_own_tmp.py) | 旧实验部署、清理或验证 | `a41b5aadbc218bd4b44ddaf2875c4df1a823be84331d2b271cc0a37db6370d9a` |
| [`test/fetch_factory_snapshot.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/fetch_factory_snapshot.py) | 旧HTTP视频接收/诊断 | `670e0dc54ccddf743580ab032dd800b6ba74e0e93d192c859a0e239343d15ea7` |
| [`test/probe_mjpeg.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/probe_mjpeg.py) | 旧HTTP视频接收/诊断 | `442058836bc112323cb0481106bc71ff978524f47e57f144624f6a3a0183f908` |
| [`test/setup_ssh_key.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/setup_ssh_key.py) | 旧SSH部署辅助 | `258d350f393c6f74d742fec7dabeecc63654f6793777f049f1b209fcae33d6de` |
| [`test/clock36_safe_20261019/stage_kernel_source.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_safe_20261019/stage_kernel_source.py) | 旧时钟/源码构建或补丁辅助 | `9b56e08378a6191a9439b1634fedc67a6def670afa10072fea88edf2b4ad3747` |
| [`test/kernel36/make_sipeed_patch.py`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/kernel36/make_sipeed_patch.py) | 旧时钟/源码构建或补丁辅助 | `55d1a5a543e7e3cbcf24d228c1e8797f53beecaa571b84e9155b63b21496da08` |
| [`test/clock36_live_20261023/probe_clock_only.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_live_20261023/probe_clock_only.sh) | 旧板端摄像头启动/管理/状态检测 | `f758b70cf5224e2f1ba91ba932041497ba9e4729fd171ce3fed9b2e2c42f0aae` |
| [`test/clock36_safe_20261019/hostcc.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/clock36_safe_20261019/hostcc.sh) | 旧时钟/源码构建或补丁辅助 | `f31be33c3e02455a343f0271cbf656b39abba9e8ec0a41801d48d4e26f7edaec` |
| [`test/kernel36/extract_sipeed_sources.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/kernel36/extract_sipeed_sources.sh) | 旧时钟/源码构建或补丁辅助 | `deccdb271c5b92a5ebf57d48dea3c55ea1be869c4f815cc682c2e75c369444ea` |
| [`test/kernel36/prepare_host_tools.sh`](https://github.com/kalapaopao/LicheeRV-Nano-GC4653/blob/8fe1a520aeb29387d9e4bc30cf44bf8c35057ac1/test/kernel36/prepare_host_tools.sh) | 旧时钟/源码构建或补丁辅助 | `9f4afdab7065df90c08e00d49436b094759e7640969b54ffc52eab89eebc03c4` |

## 清理后保留的唯一可用链路

1. **编译：** `test/clock36_live_20261023/build_long.sh`（重新编译 SDK 公共对象，不需要旧 speed-fry/build-preview-hd.sh）。
2. **板端采集/网页预览：** `test/clock36_live_20261023/camera_36long.cpp` 编译的 RISC-V 程序。
3. **受监督启动：** `test/clock36_live_20261023/live_36_supervisor.sh`（温度、MIPI、300秒自动恢复）。
4. **数据分析：** `test/clock36_live_20261023/summarize_live_5min.py` 与 `analyze_raw.py`，只用于离线分析。
5. **旧代码获取：** 通过本页永久链接看 8fe1a52，禁止直接从历史目录执行不符合现在硬件条件的旧程序。
