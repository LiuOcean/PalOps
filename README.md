# PalEdit

面向 macOS 的 Palworld 1.0 本地服务器存档编辑器。当前里程碑提供：

- 自动发现 `SaveGames/0/<WorldId>` 世界目录；
- 识别 `PlM`（Oodle）与旧 `PlZ`（zlib）存档；
- 使用 Palworld 1.0 实档完成兼容性诊断；
- 只读加载 `CharacterSaveParameterMap`，避开当前已知不兼容的 1.0 地图对象解析器；
- 浏览器本地界面，不上传存档；
- 可从 SSH 主机 `palworld-server` 拉取最新 `SaveGames` 数据；下载会先进入临时目录并通过存档发现校验，再替换本地 `Save`，原数据保存在 `.paledit-backups`；
- 提供 palworld-server 服务状态、在线玩家与白名单 RCON 运维工具，支持保存、广播、踢出、封禁、计划关服和安全重启；
- 提供服务器配置可视化查看、筛选、编辑与 JSON 导出；保存会校验远端版本、备份并原子更新 Compose，密码和凭据字段不会返回浏览器；
- 配置重启采用两阶段确认：首次勾选后申请短期一次性令牌，弹窗二次确认后才保存世界、重启容器并等待健康恢复；
- 配置项以中文名称和实际作用说明为主，Compose 环境变量名仅作为辅助诊断信息；
- RCON 指令、玩家 UID 与倒计时均由下拉菜单生成，不提供任意命令或 ID 输入框；
- 总览页读取 Palworld 官方 REST 实时指标，展示服务器 FPS、帧耗时、在线容量、运行时长、世界据点数和游戏天数；
- 展示当前世界用户、属性数据及其拥有的帕鲁，并可安全修改用户基础字段。
- 提供帕鲁世界地图，通过服务器官方 REST 接口映射当前在线玩家的实时位置，并结合本地存档展示公会据点、范围、82 个传送点与 7 座塔主塔；支持搜索定位、据点详情和玩家命令。
- 内置 Palworld 1.0 道具内部 ID 中文索引、详细说明和本地图标，可按中文名或 ID 搜索。
- 内置帕鲁 `CharacterID` 中文索引与本地图标，包含普通、Boss、Raid、塔主和任务变体。
- 内置被动技能中文名称和效果说明，可按名称、说明或技能 ID 搜索。
- 玩家帕鲁列表支持按名称、昵称、`CharacterID` 或被动技能搜索，分批加载并展开查看个体值、浓缩等级、强化加成和被动技能效果。
- 只读浏览公会、会长与成员，并关联展示公会等级、据点数量和世界坐标；公会原始块不会进入存档写回路径。

## macOS 启动

需要安装 `uv`。首次运行：

```bash
./scripts/run-macos.sh
```

脚本会创建 `.venv`、安装固定版本依赖、启动 `127.0.0.1:18765`，并用默认浏览器打开界面。选用该端口是为了避开这台 Mac 上 Unity 使用的 `8765`。

也可以执行命令行诊断：

```bash
uv run paledit inspect Save/SaveGames/0/00000000000000000000000000000000
```

## 安全边界

每次修改都会校验读取时的 SHA-256、完整备份世界、写入临时文件、重新解析，最后才原子替换 `Level.sav`。macOS 上读取当前 `PlM/Oodle`，写入使用 Palworld 仍支持的 `PlZ/zlib` 容器；内部 GVAS 字段继续使用 Palworld 原始名称、枚举、GUID 和数值类型。

项目兼容层补齐了固定版本 `palworld-save-tools` 遗漏的 Map `Int64Property` 读写分支，可解析 Palworld 1.0 的 `LevelObjectRecoverPartySaveData.PlayerLastUsedTimes`，并保持相同类型安全回写。

服务器运维接口只接受后端白名单动作。玩家操作会再次读取在线列表并验证所选 UID；安全重启固定执行 `Save` 后再发送带预设倒计时的 `Shutdown`，不会拼接或执行浏览器提供的任意命令。RCON 密码保留在 palworld-server 容器内，不会返回到浏览器。

## 更新道具索引

道具索引来自 PalDB 中文物品表所展示的游戏 `DT_ItemDataTable` 和
`DA_StaticItemDataAsset`。更新时运行：

```bash
uv run python tools/update_item_index.py
uv run python tools/update_pal_index.py
uv run python tools/sync_pst_catalog.py
```

前两步更新 PalDB 基础索引；最后一步从固定提交
`zaigie/palworld-server-tool@18df587bd9e62d0f890b8cef1c32985fa6e9ba39`
合并详细道具说明、完整帕鲁名称、被动技能和本地图标。需要审阅新版本时，先修改
`tools/sync_pst_catalog.py` 中的固定提交并核对上游数据格式，再运行同步。

没有可靠中文名称的内部条目不会自动翻译，而是保留源名称并标记为“待本地化”。
上游仓库采用 Apache-2.0；游戏名称、图标和其他美术资源的权利仍归各自权利人所有，
完整归属说明见 `src/paledit/static/catalog/THIRD_PARTY_NOTICE.txt`。
