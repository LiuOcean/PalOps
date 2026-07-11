# PalEdit

面向 macOS 的 Palworld 1.0 本地服务器存档编辑器。当前里程碑提供：

- 自动发现 `SaveGames/0/<WorldId>` 世界目录；
- 识别 `PlM`（Oodle）与旧 `PlZ`（zlib）存档；
- 使用 Palworld 1.0 实档完成兼容性诊断；
- 只读加载 `CharacterSaveParameterMap`，避开当前已知不兼容的 1.0 地图对象解析器；
- 浏览器本地界面，不上传存档；
- 写入功能默认关闭，避免在往返验证完成前损坏原档。
- 内置 Palworld 1.0 道具内部 ID 中文索引，可按中文名或 ID 搜索。
- 内置帕鲁 `CharacterID` 中文索引，包含普通、Boss、Raid、塔主和任务变体。

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

PalEdit 当前不会修改 `Save`。后续写入流程必须依次完成完整目录备份、临时文件写入、重新解析和原子替换。

## 更新道具索引

道具索引来自 PalDB 中文物品表所展示的游戏 `DT_ItemDataTable` 和
`DA_StaticItemDataAsset`。更新时运行：

```bash
uv run python tools/update_item_index.py
uv run python tools/update_pal_index.py
```

没有可靠中文名称的内部条目不会自动翻译，而是保留源名称并标记为“待本地化”。
