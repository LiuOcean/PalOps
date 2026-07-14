<div align="center">

# PalOps

一个用来管理 Palworld 1.0 专用服务器的小工具。

在浏览器里看服务器状态、管理玩家、查看地图，也可以检查和修改本地存档。

</div>

![PalOps 服务器总览](docs/images/overview.png)

管理 Palworld 服务器时，经常要在终端、日志和存档目录之间来回切。PalOps 把这些常用操作放到了一起：服务器有没有掉帧、现在谁在线、最近有没有异常、存档备份放在哪里，都可以在一个页面里看到。

它也能读取 Palworld 1.0 存档，查看玩家、帕鲁、背包、储物箱、公会和据点。需要修改存档时，PalOps 会先备份，再写入和检查，尽量避免因为一次操作损坏整个世界。

界面和说明目前以中文为主。项目可以在 macOS 上运行，也可以通过 Docker Compose 放到 Palworld 服务器旁边。

> 下面的图片来自实际运行中的 PalOps。主机名、玩家、公会和平台账号已经用色块遮住，原始截图不会提交到仓库。

## 能做什么

- 查看服务器 FPS、延迟、在线人数、运行时间和最近 7 天的变化。
- 查看在线玩家、聊天记录，并发送服务器广播。
- 保存世界、踢出或封禁玩家、安排关服，以及按固定步骤安全重启。
- 用中文查看和修改常用服务器设置。
- 从服务器拉取最新存档，在本机查看玩家、帕鲁、背包、储物箱、公会和据点。
- 搜索整个世界里的道具和帕鲁，结果会告诉你它具体在哪个玩家、背包或箱子里。
- 修改玩家基础数据和背包物品，写入前自动备份并检查文件。
- 查看、恢复和清理不同来源的本地备份。
- 在 16K 地图上查看在线玩家、公会据点、传送点和塔主塔。
- 浏览中文道具、帕鲁和被动技能图鉴，并复制游戏内部 ID。

## 界面

### 世界数据

从服务器同步存档后，PalOps 会自动找到世界并检查能否正常读取。世界数据页面分成三栏：左边选择存档，中间选择玩家、储物箱或公会，右边查看具体内容。

![PalOps 世界数据](docs/images/world-data.png)

页面上方有五个入口：

- **全局搜索**：输入道具名、帕鲁名或内部 ID，一次搜索玩家背包、储物箱和帕鲁容器。结果会写清楚具体位置。
- **储物箱**：查看世界中的物品容器、箱子名称、槽位和道具数量。这里目前以查看为主。
- **玩家**：选择玩家后，可以在“基础资料”“背包道具”“拥有的帕鲁”之间切换。
- **公会**：查看会长、成员、公会等级、据点数量和坐标，不会修改公会原始数据。
- **备份**：集中查看同步前、修改前和游戏自动生成的备份，需要时可以恢复到本地 `Save/`。

玩家页面是存档修改最常用的地方：

- “基础资料”可以修改昵称、等级、经验、属性点、饱食度和科技点。
- “背包道具”按背包分类显示槽位，可以搜索道具，也可以修改道具内部 ID 和数量。
- “拥有的帕鲁”可以按名称、昵称、`CharacterID` 或被动技能搜索，并查看个体值、浓缩等级、强化和技能效果。

保存玩家资料或背包槽位时，只会改动当前选择的本地世界。PalOps 会先备份并检查写入结果；远端服务器不会被直接替换。

### 地图

地图会把服务器里的在线玩家和本地存档里的公会据点放在一起。可以搜索目标、缩放地图，也可以单独显示传送点和塔主塔。

![PalOps 地图](docs/images/tactical-map.png)

### 图鉴

不知道内部 ID 也没关系，可以直接按中文名称、说明或类型查找。找到后再复制 ID，用于排查存档或编写脚本。

![PalOps 中文图鉴](docs/images/catalog.png)

### 服务器维护

重启服务器时，PalOps 会按“通知玩家、保存世界、等待退出、关服”的顺序执行。玩家和倒计时都从当前列表中选择，不需要手写 RCON 命令。

![PalOps 服务器维护](docs/images/safe-maintenance.png)

## 开始使用

### 在 macOS 上运行

需要：

- Python 3.12 或更高版本
- [`uv`](https://docs.astral.sh/uv/)
- [Git LFS](https://git-lfs.com/)
- 一台可以通过 SSH 或 Docker 管理的 Palworld 专用服务器

第一次运行：

```bash
brew install uv git-lfs
git lfs install
git lfs pull
./scripts/run-macos.sh
```

脚本会安装依赖，然后打开：

```text
http://127.0.0.1:18765
```

当前 macOS 启动脚本会监听 `0.0.0.0`，方便同一局域网里的设备访问。请只在可信网络中运行，或者使用防火墙限制访问。

打开 PalOps 后，先进入“设置”，选择一种连接方式：

#### SSH

适合在自己的 Mac 上运行 PalOps，再连接另一台 Palworld 服务器。

需要填写 SSH 主机名、Palworld 存档目录、Compose 文件位置和容器名称。登录仍然使用你现有的 SSH 配置，PalOps 不保存密码和私钥。

#### Docker Compose 直连

适合把 PalOps 放在 Palworld 所在的同一台机器上。PalOps 会只读挂载游戏存档，同时通过 Docker 管理服务器容器。

仓库已经提供 [`compose.direct.yaml`](compose.direct.yaml)：

```bash
PALWORLD_SERVICE_ROOT=/srv/palworld \
PALWORLD_SAVE_ROOT=/srv/palworld/Pal/Saved \
docker compose -f compose.direct.yaml up -d --build
```

默认只允许本机访问 `127.0.0.1:18765`。从其他电脑访问时，推荐使用 SSH 转发：

```bash
ssh -L 18765:127.0.0.1:18765 palworld-server
```

Docker socket 拥有管理宿主机 Docker 的权限，不要把 PalOps 直接开放到公网。

## 存档放在哪里

PalOps 使用仓库里的 `Save/` 保存本地存档副本。世界目录不需要手工填写，它会自动查找：

```text
Save/SaveGames/0/<WorldId>/Level.sav
```

如果只想检查一个存档，可以运行：

```bash
uv run palops inspect Save/SaveGames/0/<WorldId>
```

“从服务器同步”不会直接覆盖本地数据。新存档会先复制到临时目录，确认能够正常识别后才替换 `Save/`，旧版本会放进 `.paledit-backups/`。

PalOps 中的存档修改也只作用于本地副本，不会在服务器运行时直接替换远端存档。

## 修改存档时会做什么

每次写入前，PalOps 都会：

1. 检查文件有没有在读取后被其他程序改动。
2. 备份当前世界。
3. 先写入临时文件。
4. 重新读取临时文件，确认还能正常解析。
5. 检查通过后，再替换原文件。

如果其中一步失败，原存档不会被替换。

Palworld 更新后，存档格式可能发生变化。升级游戏或解析依赖后，建议先对备份副本测试，不要直接拿唯一一份存档尝试。

## 本机数据和隐私

这些目录和文件不会提交到 Git：

- `Save/`：从服务器同步的本地存档
- `.paledit-data/settings.json`：服务器位置、角色选择和刷新时间
- `.paledit-data/chat.sqlite3`：聊天记录
- `.paledit-data/metrics.sqlite3`：最近 7 天的服务器数据
- `.paledit-data/box-targets.json`：批量箱子任务的目标
- `.paledit-backups/`：同步和修改前的备份
- `.artifacts/`：本地测试文件和截图原图

请不要在 Issue、截图、测试或提交中放入真实的玩家 UID、昵称、世界 ID、箱子 GUID、SSH 主机名、本机绝对路径、密码、Token、Cookie 或私钥。

## 存档支持情况

- 可以识别 Palworld 1.0 使用的 `PlM`（Oodle）存档和旧的 `PlZ`（zlib）存档。
- 当前读取和写入流程使用 Palworld 1.0 实际存档测试。
- 如果某一部分存档还不能可靠解析，PalOps 会保持只读或拒绝写入。
- 写出的存档使用 Palworld 仍然支持的 `PlZ/zlib` 格式。

## 开发

安装开发依赖并运行测试：

```bash
uv sync --extra dev
uv run pytest
```

启动本地服务：

```bash
uv run palops serve --host 127.0.0.1
```

主要代码在 `src/paledit/`：

```text
api.py              网页和接口入口
remote.py           连接 SSH、Docker、REST 和 RCON
save.py             识别存档和查找世界目录
parser.py           读取世界存档
world.py            玩家、公会、箱子和存档修改
backups.py          备份、恢复和删除
metrics_history.py  保存服务器历史数据
chat.py             保存聊天记录
static/             网页界面、地图和图鉴
```

更新本地图鉴：

```bash
uv run python tools/update_item_index.py
uv run python tools/update_pal_index.py
uv run python tools/sync_pst_catalog.py
uv run python tools/update_skill_ranks.py
```

这些脚本使用固定的上游版本。更新版本时，请一起检查数据变化和对应的许可文件。

## 第三方内容

PalOps 自己的代码使用 [MIT License](LICENSE)。仓库里的第三方代码和游戏资源仍然使用它们原来的许可：

- 图鉴数据、图标和地图瓦片来自 `palworld-server-tool` 的固定版本，上游项目使用 Apache-2.0。
- 地图坐标和点位数据的来源写在地图 notice 中。
- Palworld 的名称、图标、地图和其他游戏素材归 Pocketpair 及对应权利人所有。
- 界面使用的 Phosphor Icons 保留原许可。

详细来源：

- [`src/paledit/static/BRAND_ASSET_NOTICE.txt`](src/paledit/static/BRAND_ASSET_NOTICE.txt)
- [`src/paledit/static/catalog/THIRD_PARTY_NOTICE.txt`](src/paledit/static/catalog/THIRD_PARTY_NOTICE.txt)
- [`src/paledit/static/map/THIRD_PARTY_NOTICE.txt`](src/paledit/static/map/THIRD_PARTY_NOTICE.txt)

PalOps 是非官方项目，与 Pocketpair 或 Valve 没有合作或从属关系。

## 参与贡献

欢迎提交 Issue 和 Pull Request。

如果改动涉及存档写入或服务器操作，请说明怎么备份、怎么恢复，以及你实际做过哪些测试。文档和测试请使用示例数据，不要提交真实服务器或玩家信息。

## License

[MIT](LICENSE) © 2026 PalOps contributors
