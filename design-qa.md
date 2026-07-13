# PalEdit 运维界面 Design QA

- Source visual truth: `local-artifacts/generated-images/00000000-0000-0000-0000-000000000101/exec-00000000-0000-0000-0000-000000000105.png`
- Implementation screenshot: `~/Projects/Tools/Game/PalEdit/.artifacts/ui/operations-final-default.jpg`
- Full target-size implementation evidence: `~/Projects/Tools/Game/PalEdit/.artifacts/ui/operations-1440x1024.jpg`
- Combined comparison: `~/Projects/Tools/Game/PalEdit/.artifacts/ui/design-qa-comparison-final.jpg`
- Viewport: target 1440 x 1024; final focused browser evidence 1280 x 720
- State: 运维 / 常用操作；palworld-server 在线；3 名玩家在线；RCON 已连接；所有确认框未勾选

## Full-view comparison evidence

方案 3 与实现采用相同的顶部导航、主操作区加右侧上下文栏、深色森林绿表面、酸性荧光绿主动作和分步安全重启结构。实现保留了更明确的“表单生成、无需输入指令或玩家 ID”产品约束，并在 1440 x 1024 证据中保持主动作、右栏状态和常用操作同屏。

## Focused region comparison evidence

最终 1280 x 720 浏览器截图用于检查顶部导航、重启步骤、右栏状态和真实图标清晰度。Phosphor 图标字体替换了首轮的字母占位与纯数字步骤表达；图标文件和许可证均随项目本地提供，不依赖外部 CDN。无需额外局部截图，因为关键表单、图标与右栏文字在该截图中均可读。

## Required fidelity surfaces

- Fonts and typography: 使用系统 SF Pro / PingFang SC 字体栈；标题、正文和小型状态文字层级与方案一致，无异常换行或截断。
- Spacing and layout rhythm: 方案的宽主区、窄上下文栏和紧凑行式步骤得到保留；响应式断点在 980px 和 700px 下重排。
- Colors and visual tokens: 近黑、深森林绿、酸性绿、琥珀与危险红均由集中 CSS token 管理，状态对比明确。
- Image quality and asset fidelity: 界面不需要位图内容；操作图标使用本地 Phosphor 2.1.2 字体资产，品牌 P 标记沿用项目现有视觉。
- Copy and content: 中文运维文案明确区分安全重启、保存、广播、玩家管理和高级白名单指令，并明确不允许手写指令与 ID。

## Interaction and runtime evidence

- 主导航和三个运维 tab 可切换。
- 玩家操作、玩家目标、指令、广播模板和倒计时均为下拉菜单。
- 玩家下拉由实时 REST 玩家列表生成，仅显示昵称与等级。
- 未勾选确认框时，安全重启、玩家操作和高级指令按钮均保持 disabled。
- 浏览器控制台错误：0。
- 自动化测试：19 passed。
- 未点击任何执行按钮；未发送保存、广播、踢出、封禁、关服或重启命令。

## Comparison history

1. P1: 初始实现将容器状态与玩家列表放入同一个 `Promise.all` 错误边界，空响应的 `ShowPlayers` 超时会把健康服务器错误显示为不可用。
   - Fix: 在线玩家改用容器内官方 REST API 只读端点；RCON 密码仍只在 palworld-server 容器环境中展开，不返回 PalEdit。
   - Post-fix evidence: 浏览器显示服务器“在线”、RCON“已连接”和 3 名在线玩家。
2. P2: 首轮实现使用字母标记代替方案中的操作图标。
   - Fix: 本地引入 Phosphor 2.1.2 regular 图标字体，为安全重启、广播、保存、倒计时和电源步骤提供一致图标。
   - Post-fix evidence: 最终默认窗口截图与合并对比图显示真实图标并保持原有布局。
3. P2: 1280 x 720 首次截图裁掉下方主动作，无法代表目标画布。
   - Fix: 补充 1440 x 1024 同状态全视图，并将最终 1280 x 720 截图只作为图标与首屏聚焦证据。
   - Post-fix evidence: `operations-1440x1024.jpg` 显示确认框、主动作、操作结果与右栏完整区域。

## Findings

无剩余 P0、P1 或 P2 问题。

## Follow-up polish

- P3: 后续可为操作日志增加持久化，但这不影响当前运维主流程和安全边界。

final result: passed
