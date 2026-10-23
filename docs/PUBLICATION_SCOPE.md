# Public 仓库与本地完整归档

## 保存位置

Windows 项目根目录：`D:\study\LicheeRV`

**这是本地研究档案的唯一写入项目位置。** 本仓库在这个目录原位 Git 初始化，并不会自动删除或迁移源文件。

完整归档本地仍包含：

- `speed-fry/workspace/`：第三方 LicheeRV SDK、host-tools 交叉编译器。
- `test/vendor_linux/`、`test/vendor_osdrv/`、`test/vendor_sipeed_*/`：上游参考源。
- `test/kernel36/kernel_src/`、`test/kernel36/kernel_out/`：内核副本、编译输出。
- `test/**/results/`：原始 NV21、RAW12、Bayer、YUV、BMP、JPEG 和测试日志。
- `licheervnano-gc4653-80fps-20261018/**/workspace.tar.gz`：完整历史工作区归档。

GitHub Public 仅发布精简且可复现的**自研源码、测试脚本、时序补丁、实验摘要（JSON/CSV）、技术文档、经过审阅的示意照片/图表**。超大文件和第三方 SDK 的来源、用途在文档中标注。

## 排除原则

1. **文件过大**：本地研究档案原始体量约 1.85 GiB、数万文件；GitHub 单文件限制为 100 MiB，工具链/SDK 不适合放入项目源码。
2. **许可与重复**：上游 BSP、内核、交叉编译器请通过原官方链接获取；不把其副本视为自有成果。
3. **隐私**：个人信息、SSH 私钥、Access Token、.env、账户登录凭据、含他人面部/私人空间的原始画面不上传。精选图已裁去相关区域，仅用于说明现象。
4. **构建冗余**：编译产物、对象文件、缓存、视频流、旧日志不放 Git；关键指标以精简实验 JSON/Markdown 和报告呈现。
5. **真实性**：所有结果明确“通过”“问题”“未测”，不因公开传播而提升实验的验收等级。

### 如何在本地完整复原

在原实验电脑上，保留 `D:\study\LicheeRV` 整体目录即可。Git `.gitignore` 只是停止跟踪和上传，并**不会删除被忽略的本地文件**。

如从 GitHub 克隆到另一台电脑，需要另行取得匹配的 SDK、交叉工具链与原始大样本（由持有者合法保管），不能从这个 Public 仓库单独恢复所有 GB 级原始证据。

## 大型证据的指引

- 70 FPS：`test/over70_lab/results/` 下有若干原始 NV21 与运行统计。
- 72 FPS：`test/stable_72p18_raw1080/snapshot/results/` 下有 Bayer 文件与错误计数。
- 80 FPS：`speed-fry/stripe-diagnostic/` 下有上下游诊断 RAW/YUV 和原始日志。
- 原始项目打包：`licheervnano-gc4653-80fps-20261018/licheervnano-gc4653-80fps-20261018/`。

## 发布检查

发布前需查看 `git status`、`git diff --cached --stat`、待发布文件列表，并执行敏感内容审查。**任何改变 .gitignore 的修改都必须重新检查**，以防大文件、原始照片或私钥意外进入历史。`n