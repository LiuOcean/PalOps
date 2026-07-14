# PalEdit

面向 macOS 的 Palworld 1.0 本地服务器存档编辑器。当前里程碑提供：

- 自动发现 `SaveGames/0/<WorldId>` 世界目录；
- 识别 `PlM`（Oodle）与旧 `PlZ`（zlib）存档；
- 使用 Palworld 1.0 实档完成兼容性诊断；
- 只读加载 `CharacterSaveParameterMap`，避开当前已知不兼容的 1.0 地图对象解析器；
- 浏览器本地界面，不上传存档；
- 可从 SSH 主机 `palworld-server` 拉取最新 `SaveGames` 数据；下载会先进入临时目录并通过存档发现校验，再替换本地 `Save`，原数据保存在 `.paledit-backups`；
- 提供备份索引、本地安全恢复和受控删除，统一汇总服务器同步前快照、PalEdit 写入前备份、游戏自动备份与批量箱子编辑备份；恢复前会校验哈希、再次备份当前世界并原子替换，删除会校验扫描时间与大小，恢复前安全快照创建后 24 小时内禁止删除，所有操作均不会修改远端 palworld-server；
- 提供 palworld-server 服务状态、在线玩家与白名单 RCON 运维工具，支持保存、广播、踢出、封禁、计划关服和安全重启；
- 提供服务器聊天查看与本地持久化：首次回收 Docker 仍保留的最近 7 天日志，之后在聊天页每 5 秒、其他页面每 30 秒按时间戳增量同步到 `.paledit-data/chat.sqlite3`，远端不可用时仍可浏览已保存记录；
- 提供服务器配置可视化查看、筛选、编辑与 JSON 导出；保存会校验远端版本、备份并原子更新 Compose，密码和凭据字段不会返回浏览器；
- 配置重启采用两阶段确认：首次勾选后申请短期一次性令牌，弹窗二次确认后才保存世界、重启容器并等待健康恢复；
- 配置项以中文名称和实际作用说明为主，Compose 环境变量名仅作为辅助诊断信息；
- RCON 指令、玩家 UID 与倒计时均由下拉菜单生成，不提供任意命令或 ID 输入框；
- 总览页读取 Palworld 官方 REST 实时指标，展示服务器 FPS、帧耗时、在线容量、运行时长、世界据点数和游戏天数；后端每 60 秒采样容器健康、指标与管理链路延迟到 `.paledit-data/metrics.sqlite3`，以健康大盘和趋势图展示，并循环裁剪到最近 7 天、最多 10,080 个样本；
- 展示当前世界用户、属性数据及其拥有的帕鲁，并可安全修改用户基础字段。
- 提供 16384×16384 的本地高分辨率瓦片地图，通过服务器官方 REST 接口映射当前在线玩家的实时位置，并结合本地存档展示公会据点、范围、82 个传送点与 7 座塔主塔；支持按视口加载、800% 缩放、搜索定位、据点详情和玩家命令。
- 内置 Palworld 1.0 道具内部 ID 中文索引、详细说明和本地图标，可连续浏览全部条目，也可按中文名或 ID 筛选。
- 内置帕鲁 `CharacterID` 中文索引与本地图标，包含普通、Boss、Raid、塔主和任务变体。
- 内置被动技能中文名称、效果说明和品级，可按名称、说明或技能 ID 搜索。
- 玩家帕鲁列表支持按名称、昵称、`CharacterID` 或被动技能搜索，分批加载并展开查看个体值、浓缩等级、强化加成、被动技能品级和效果。
- 只读浏览公会、会长与成员，并关联展示公会等级、据点数量和世界坐标；公会原始块不会进入存档写回路径。

## macOS 启动

需要安装 `uv` 和 Git LFS。首次运行：

```bash
./scripts/run-macos.sh
```

脚本会创建 `.venv`、安装固定版本依赖、启动 `127.0.0.1:18765`，并用默认浏览器打开界面。选用该端口是为了避开这台 Mac 上 Unity 使用的 `8765`。

地图瓦片固定来自 `palworld-server-tool v0.12.0`，共 5461 个 z0–z6 PNG，由 Git LFS 管理。如果启动脚本提示瓦片不完整，先运行 `git lfs pull`。浏览器只加载当前缩放层级和视口附近的瓦片，不会一次载入完整 16K 地图。

也可以执行命令行诊断：

```bash
uv run paledit inspect Save/SaveGames/0/00000000000000000000000000000000
```

## 安全边界

每次修改都会校验读取时的 SHA-256、完整备份世界、写入临时文件、重新解析，最后才原子替换 `Level.sav`。macOS 上读取当前 `PlM/Oodle`，写入使用 Palworld 仍支持的 `PlZ/zlib` 容器；内部 GVAS 字段继续使用 Palworld 原始名称、枚举、GUID 和数值类型。

项目兼容层补齐了固定版本 `palworld-save-tools` 遗漏的 Map `Int64Property` 读写分支，可解析 Palworld 1.0 的 `LevelObjectRecoverPartySaveData.PlayerLastUsedTimes`，并保持相同类型安全回写。

服务器运维接口只接受后端白名单动作。玩家操作会再次读取在线列表并验证所选 UID；安全重启固定执行 `Save` 后再发送带预设倒计时的 `Shutdown`，不会拼接或执行浏览器提供的任意命令。RCON 密码保留在 palworld-server 容器内，不会返回到浏览器。

聊天同步只读访问 `palworld-server` 容器日志，并仅保存 `[CHAT]` 行。聊天内容在浏览器中通过文本节点渲染，不作为 HTML 执行。本地 SQLite 数据库已加入 Git 忽略规则；Docker 日志轮转或容器重建前尚未同步的旧消息无法恢复。

## 更新道具索引

道具索引来自 PalDB 中文物品表所展示的游戏 `DT_ItemDataTable` 和
`DA_StaticItemDataAsset`。更新时运行：

```bash
uv run python tools/update_item_index.py
uv run python tools/update_pal_index.py
uv run python tools/sync_pst_catalog.py
uv run python tools/update_skill_ranks.py
```

前两步更新 PalDB 基础索引；第三步从固定提交
`zaigie/palworld-server-tool@7df5ec40c5d3f3ef50200f2048dc116a0b9938bf`（v0.12.0）
合并详细道具说明、完整帕鲁名称、被动技能和本地图标；最后一步补入 PalDB 当前页面展示的被动技能品级。需要审阅新版本时，先修改
`tools/sync_pst_catalog.py` 中的固定提交并核对上游数据格式，再运行同步。

没有可靠中文名称的内部条目不会自动翻译，而是保留源名称并标记为“待本地化”。
上游仓库采用 Apache-2.0；游戏名称、图标和其他美术资源的权利仍归各自权利人所有，
完整归属说明见 `src/paledit/static/catalog/THIRD_PARTY_NOTICE.txt`。
