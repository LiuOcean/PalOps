# PalOps 战术指挥台 Design QA

- 工作台基线：`cc380fb`
- 上游对比：`zaigie/palworld-server-tool v0.12.0` / `7df5ec40c5d3f3ef50200f2048dc116a0b9938bf`
- 桌面三栏、低高度桌面、双栏骨架与规则页均完成截图验收；截图属于本地测试产物，不记录绝对路径。

## 信息架构与视觉结果

- 一级入口收敛为总览、世界、地图、管理、图鉴；二级页面均由 Hash 路由定位。
- 1440px 下为数据源、资源列表、详情三栏；900px 隐藏数据源并保持双栏；390px 使用资源列表/详情单栏钻取和固定五项底部导航。
- 保留森林暗色与荧光绿，世界区使用蓝色、管理区使用琥珀色、危险动作使用珊瑚色。现有地图、道具、帕鲁和 Phosphor 资源继续作为唯一美术来源。
- 总览显示存档新鲜度、最近备份、解析能力和关注事项；图鉴为单一分类页签；维护页只保留受控的安全重启主流程。

## 浏览器验收

| 视口 | 布局与结果 |
| --- | --- |
| 1440×900 | 三栏可见；侧栏固定；容器列表和详情独立滚动。 |
| 1280×720 | 文档尺寸与视口同为 1280×720；侧栏底部为 720；标题与上下文导航保持可见。 |
| 900×900 | 数据源列隐藏，资源/详情双栏；加载完成后显示容器列表；无横向或整页溢出。 |
| 390×844 | 文档宽度 390；五个底部入口高度均为 57px；玩家列表与详情单栏切换，返回入口有效。 |

- 直接打开 `#/world/players` 后保持在玩家页，单世界快照会自动只读加载，不会跳回储物箱。
- Hash 后退从 `#/manage/rules` 正确回到 `#/manage/players`；切换前后工作台滚动位置均为 0。
- 当前设置选中的角色只出现一个“我的角色”标识；未修改表单时保存按钮禁用并显示“尚无变更”。
- 备份按 3 个日期/来源组展示，共 16 条；行内无危险按钮，恢复、删除和技术路径集中在选中项详情。
- 规则分组顺序为游戏体验、世界与据点、备份维护、连接、高级；高级默认折叠，未修改时保存禁用。
- 浏览器控制台 error/warning：0。

## 高分辨率地图验收

- 地图底图由单张 4096×4096 WebP 升级为 z0–z6 本地瓦片金字塔：5461 张 256px PNG，最高原生分辨率 16384×16384。
- 瓦片来源固定为 `palworld-server-tool v0.12.0@7df5ec40`，由 Git LFS 管理；低清占位图从同一瓦片金字塔生成，加载前后不切换坐标系。
- 地图世界边界同步为瓦片原始边界 `X -1099400…349400 / Y -724400…724400`，避免玩家与据点标记出现约 10 万单位的系统偏移。
- 1440×900 默认使用 z3 / 2048px，仅加载 64 张瓦片；1280×720 默认使用 z2 / 1024px，仅加载 16 张瓦片。
- 放大到 800% 自动切换为 z6 / 16384px，只保留当前视口附近 121 张瓦片；键盘平移后瓦片键从视口范围重新计算，没有一次加载全部 4096 张 z6 瓦片。
- 地图控制台改为可收起浮层，地图主体在桌面端回收原控制栏宽度；详情栏在 1180px 以下移到地图下方。
- 支持鼠标位置缩放、拖动、双击、方向键、`+`、`-`、`0`，并显示当前瓦片层级、像素分辨率、缩放比例和鼠标世界坐标。
- 瓦片层不再随父容器进行 GPU 二次缩放，而是按设备像素对齐后直接绘制到最终屏幕尺寸；瓦片就绪后低清占位图透明度归零，避免两层混合造成地名和内嵌标注发糊。
- 1280×720、250% 实测使用 z3 / 2048px：瓦片原图 256px、最终显示 180.5px、瓦片层 `transform: none`、占位图透明度 0、破损瓦片 0。
- 玩家、据点、传送点和塔主塔覆盖层同样按最终设备像素定位，不再采用“父层放大、标记反向缩小”；玩家与据点文字及全部祖先节点在 250% 下均为 `transform: none`，技术标签字号统一为 10px。
- 打开本地世界后，在线玩家和据点均能显示；据点范围圈独立按比例改变像素尺寸，不再参与或影响文字层栅格化。
- 390×844 默认收起图层控制台，地图宽度 366px；五项底部导航保留，地图工具按钮均不低于 44px，无横向溢出。
- 全部实测瓦片 `naturalWidth > 0`，浏览器控制台 error/warning：0。

## 解析与安全验收

- `/api/world/snapshot` 在同一份只读快照上返回摘要、用户、容器、公会和据点；解析修订为 `paledit-1.0-v0.12-compat-1`。
- 本地世界解析前后 `Level.sav` 逐字节一致；用户、容器和公会数据均由当前存档读回。
- 从目标服务器只读下载到随机临时目录的最新快照解析成功，解析前后文件逐字节一致；报告不记录真实昵称、等级、数量或临时路径。
- 快照按 SHA-256 换代；并发访问只执行一次解码；显式失效后重新解码。
- typed 能力和 raw MapObject 扫描回退同时上报；未知 MapObject 字节仍保持不透明，写入边界没有扩大。
- 目录来源固定到 v0.12.0 commit；保留 2466 道具、1156 CharacterID 与既有本地图标覆盖率。
- 未执行远端同步、保存、广播、踢出、封禁、关服、重启或覆盖操作。

## 自动化验证

- `pytest -q`：66 passed。
- Python compileall：通过。
- JavaScript `node --check`：通过。
- HTML parser：通过。
- `zsh -n scripts/run-macos.sh`：通过。
- 瓦片数量与 Git LFS 属性：5461 / `filter=lfs`。
- `git diff --check`：通过。

## Findings

无剩余 P0、P1 或 P2 问题。

远端快照仅下载到临时目录。未改动仓库 `Save/`，也未在目标服务器执行保存、停服、重启或覆盖；远端与本地快照的新鲜度及哈希仅在本地验收，不写入报告。

final result: passed

---

## Backup Diff Design QA

### Scope

- Surface: PalOps backup browser and read-only backup diff workspace.
- Reference: Product Design selection-state mock and detailed-result mock from the current design session.
- Implementation evidence: `palops-backup-diff-selection-impl.png` and `palops-backup-diff-result-impl.png` in the session-local visualization directory. These captures are intentionally not tracked because they contain local runtime data.
- Comparison evidence: `palops-backup-diff-selection-compare.png`, `palops-backup-diff-result-compare.png`, and `palops-backup-diff-result-focus-compare.png` in the same session-local directory.
- Desktop viewport: 1440 × 1024 CSS pixels.
- Responsive viewport: 390 × 844 CSS pixels.

### Required states

| State | Result |
| --- | --- |
| No selection | Existing backup browser remains usable; comparison tray stays hidden. |
| One version selected | Tray identifies the selected version and asks for a second version. |
| Two versions selected | Older backup becomes the default base, newer backup becomes the target; swap remains available. |
| Invalid pair | Comparison is disabled when the versions have no common world or no comparable `Level.sav`. |
| Loading | Dedicated progress panel explains parsing and cache behavior. |
| Ready | Summary, categories, search, type filters, important-only filter, and paginated changes are visible. |
| Error | Failure is rendered in the diff workspace without mutating backups. |
| Mobile | Controls stack vertically, categories remain reachable, and the existing bottom navigation is preserved. |

### Visual comparison

- Hierarchy matches the references: version selection precedes the summary, then category navigation and field-level changes.
- The implementation reuses PalOps typography, lime/blue status colors, surfaces, borders, icons, and compact operator density.
- The selection state keeps the existing backup details panel instead of replacing it with a duplicate comparison summary; the persistent comparison tray carries the A/B state.
- The result state uses five summary cards rather than a single compressed strip so all totals remain legible at the existing PalOps content width.
- Field-level rows keep base and target values aligned and use color only as a secondary status cue.

### Interaction verification

| Interaction | Result |
| --- | --- |
| Select two newest backups | Passed; base and target were ordered chronologically. |
| Start comparison | Passed; 3,100 semantic changes loaded from the real local backup pair. |
| Cached rerun | Passed; the result summary reported a cache hit. |
| Category + modified filter | Passed; guild changes narrowed to 18 rows. |
| Important-only filter | Passed; the same selection narrowed to 2 rows. |
| Desktop responsive check | Passed. |
| 390 px mobile check | Passed; no visible horizontal clipping in the tested states. |

### Issue history

1. P2: asset caching initially displayed the new markup with an older stylesheet. Fixed by versioning the changed CSS and JavaScript asset URLs.
2. P2: selecting the newest backup first initially reversed the expected comparison direction. Fixed by sorting the initial pair by creation time while keeping the explicit swap action.
3. P3 tooling note: the in-app browser connection did not expose a stable console-log reader. Final page loads, API requests, interactive states, and server responses completed without a surfaced runtime error state.

### Automated verification

- Full pytest suite passed.
- JavaScript syntax check passed.
- `git diff --check` passed.

### Final result

passed

---

## Backup Diff Timeline Redesign QA

### Audit scope

- Selected reference: Product Design concept 3, a change-timeline workspace with a persistent evidence inspector.
- Reference image: `/Users/lac_123_1234/.codex/generated_images/019f662d-38be-7bb1-80c2-c46e12e02f54/exec-43213712-d084-4714-b197-01740bfcb1b0.png`.
- Live state: `http://127.0.0.1:18766/#/world/backups/compare` with a real local backup pair.
- Truth constraint: the API exposes two snapshot times but no exact time for each intermediate change, so timeline nodes are explicitly labeled as changes within the interval instead of presenting invented timestamps.

### Reference comparison

| Area | Result |
| --- | --- |
| Version context | Passed; the base and target snapshots, interval, same-world validation, swap, and rerun controls fit in one compact desktop row. |
| Narrative hierarchy | Passed; snapshot boundaries frame a category-based change timeline and the summary remains visible above it. |
| Evidence inspection | Passed; selecting a business object updates a persistent before/after inspector without losing timeline position. |
| Density | Passed; the desktop workspace has bounded internal scrolling and long field values are clamped with their full value available as a title. |
| Responsive layout | Passed at 390 x 844; the page has no horizontal overflow and selecting an item reveals the inspector below the timeline. |

### Interaction verification

| Interaction | Result |
| --- | --- |
| Object selection | Passed; selected state and inspector content update together. |
| Category filter | Passed; the guild category narrowed the real result to 5 objects and 31 fields. |
| Combined filters | Passed; guild, modified-only, and important-only narrowed the result to 2 objects and 2 fields. |
| Pagination and request ownership | Passed; existing page and latest-request behavior remain intact. |
| Console | Passed; no browser console errors were observed during the inspected flow. |

### Resolved findings

1. P2: the version context wrapped into two rows at 1440 px. Fixed with a compact single-row desktop layout.
2. P2: the comparison workspace stretched with the full result and weakened the timeline/inspector relationship. Fixed with a bounded desktop workspace and independent scrolling.
3. P2: legacy summary styles split the primary count awkwardly. Fixed with one headline and separate contextual copy.
4. P2: verbose values overwhelmed the inspector and a raw owner label leaked implementation language. Fixed with value clamping and the user-facing `对象本身` label.

### Automated verification

- Full suite reached 119 passing tests with one stale static signature assertion; that assertion was updated for the new optional reveal parameter.
- The targeted static UI suite then passed: 2 tests.
- JavaScript syntax check passed.
- Git whitespace validation passed.

### Final result

passed

---

## Backup Diff Information Architecture QA

### Audit scope

- Reference: `/Users/lac_123_1234/.codex/generated_images/019f65db-881d-7670-92b4-c78cbb9eef71/exec-b783a279-0518-481a-a8e7-445ad73d3930.png`.
- Live state: `http://127.0.0.1:18766/#/world/backups/compare` with a real local backup pair.
- Primary objective: make the result understandable at business-object level before exposing technical field changes.

### Reference comparison

| Area | Result |
| --- | --- |
| Version context | Passed; two bordered version cards, swap control, same-world state, and rerun action precede the result. |
| Summary hierarchy | Passed; one integrated overview strip now replaces five competing metric cards. |
| Category navigation | Passed; the left rail mirrors the reference and reports business-object counts. |
| Detail density | Passed; player, inventory, pal, container-slot, guild-member, and base changes roll up to their owning object. |
| Progressive disclosure | Passed; the first object is open for orientation and remaining field details expand on demand. |
| Responsive layout | Passed at the active desktop viewport; the rerun action no longer collapses vertically. |

### Data integration evidence

- The real comparison is summarized as 144 affected business objects instead of 3,069 flat field rows.
- The category totals resolve to 14 players, 101 containers, 5 guilds, 1 world summary, and 23 files.
- Field-level evidence remains available inside each object group and keeps the base and target values aligned.

### Interaction verification

| Interaction | Result |
| --- | --- |
| Container category | Passed; narrowed to 101 objects and 1,470 field changes. |
| Modified-only filter | Passed; narrowed the container state to 51 objects and 558 field changes. |
| Expand/collapse | Passed; the first object toggled without losing filter or pagination state. |
| Restore all changes | Passed; returned to 144 objects and 3,069 field changes. |

### Automated verification

- 120 pytest tests passed in 138.63 seconds.
- JavaScript syntax check passed.
- Targeted backup diff and static UI checks passed.

### Final result

passed

---

## Backup Diff Polish QA

### Audit scope

- Flow: select two backups, generate a semantic diff, narrow the result, rerun the comparison, and recover from a failed request.
- Target: the existing PalOps desktop backup workflow and its read-only comparison workspace.
- Accessibility checks in this pass: status announcements, disabled invalid actions, explicit validation copy, and busy-state exposure. Keyboard order and screen-reader output still require dedicated assistive-technology testing.

### Flow health

| Step | Health | Evidence |
| --- | --- | --- |
| 1. Select base and target versions | Passed | The pair is ordered chronologically and the common-world check enables comparison. |
| 2. Generate the comparison | Passed | The cached semantic result rendered with summary totals, categories, filters, and paginated rows. |
| 3. Narrow the result | Passed | Category, change type, and important-only filters produced one internally consistent final state. |
| 4. Rerun the comparison | Passed | Query, category, change type, important-only, pagination, and loading state reset before the new result appeared. |
| 5. Validate an invalid pair | Passed | Selecting the same version shows a specific error and disables the comparison action. |
| 6. Recover from a request failure | Passed | The error panel removes the irrelevant progress note and exposes both retry and return actions; retry restores the result after the service is available. |

### Resolved findings

1. P1: overlapping filter requests could leave controls and rows describing different filters. Fixed with request cancellation and latest-request ownership.
2. P2: rerunning or changing the version pair could inherit the previous result filters. Fixed with an explicit comparison-state reset.
3. P2: the failure state had no direct recovery action. Fixed with in-place retry and return-to-list actions.
4. P3: invalid version copy grouped multiple causes into one message. Fixed with separate messages for missing versions, identical versions, and no common world.
5. P3: asynchronous result changes did not expose a busy state. Fixed with `aria-busy` on the loading and diff result regions.

### Verification

- Targeted backup and UI tests passed.
- JavaScript syntax check passed.
- Real local backup flow passed for cached load, combined filters, rerun reset, invalid-pair validation, failure rendering, and retry recovery.
- Visual inspection passed at the existing desktop viewport; no new visual system or component language was introduced.

### Final result

passed
