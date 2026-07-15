# 安装与部署

PalOps 支持两种服务器连接方式。两种方式使用相同的网页界面和本地数据结构，区别在于服务器命令和存档文件从哪里读取。

| 方式 | PalOps 运行位置 | 服务器访问方式 | 适用场景 |
| --- | --- | --- | --- |
| SSH | 管理员自己的 Mac 或其他管理机 | 通过 SSH 执行 Docker 命令，通过 `rsync` 拉取远端存档 | 不希望在游戏服务器上额外运行管理容器 |
| Docker Direct | 与 Palworld 使用同一个 Docker daemon 的主机 | 直接读取映射目录，并通过 Docker socket 管理容器 | PalOps 与 Palworld 部署在同一台主机 |

无论选择哪种方式，第一次拉取代码后都需要取得 Git LFS 资源，否则地图瓦片会保留为文本指针：

```bash
git lfs install
git lfs pull
```

## SSH：在管理机运行

SSH 模式适合在自己的 Mac 上运行 PalOps，再连接远端 Palworld 主机。需要：

- Python 3.12 或更高版本
- [`uv`](https://docs.astral.sh/uv/)
- [Git LFS](https://git-lfs.com/)
- 本机可直接执行的 `ssh` 与 `rsync`
- 已配置公钥登录的 SSH 主机名或别名
- 远端可用的 Docker CLI，以及正在运行的 Palworld 容器

macOS 首次运行：

```bash
brew install uv git-lfs
git lfs install
git lfs pull
./scripts/run-macos.sh
```

启动脚本会监听 `0.0.0.0:18765`，同时在本机打开：

```text
http://127.0.0.1:18765
```

配置 PalOps 前，建议先确认 SSH 能在无交互模式下工作：

```bash
ssh -G palworld-server
ssh -o BatchMode=yes palworld-server true
```

随后在“设置”页面填写：

| 设置项 | SSH 模式中的含义 | 示例 |
| --- | --- | --- |
| 连接方式 | 选择 `SSH` | `ssh` |
| SSH 主机 | `~/.ssh/config` 中的别名，或可直接连接的主机名 | `palworld-server` |
| 公网访问地址 | 玩家从公网连接时使用的域名或 IP，可包含端口；用于延迟采样 | `play.example.com:8211` |
| 存档目录 | 远端主机上包含 `SaveGames/` 的绝对路径 | `/srv/palworld/Pal/Saved` |
| Compose 路径 | 远端主机上的 Compose 文件绝对路径 | `/srv/palworld/compose.yaml` |
| Docker 路径 | 远端主机上 Docker CLI 的绝对路径 | `/usr/local/bin/docker` |
| 容器名称 | Palworld 的 Compose 服务名和运行容器名 | `palworld-server` |
| RCON 工具路径 | Palworld 容器内部的 RCON CLI 路径 | `/usr/bin/rcon-cli` |
| RCON 端口 | Palworld 服务器的 RCON TCP 端口 | `25575` |

SSH 模式使用现有的 OpenSSH 配置和密钥代理。PalOps 不保存 SSH 密码或私钥，并使用 `BatchMode=yes`，需要交互式输入密码的连接会直接失败。存档同步通过 `rsync` 先写入本地临时目录，验证成功后才替换本地 `Save/`。

## Docker Direct：与 Palworld 同机部署

Direct 模式不经过 SSH。PalOps 直接映射 Palworld 服务目录和存档目录，并通过 `/var/run/docker.sock` 查询或管理现有的 Palworld 容器。

需要：

- Linux、Docker Desktop 或 OrbStack 等可运行 Linux 容器的环境
- Docker Compose v2
- PalOps 与 Palworld 使用同一个 Docker daemon
- 宿主机存在 `/var/run/docker.sock`
- Palworld 服务目录和存档目录允许 Docker 做 bind mount

仓库提供 [`compose.direct.yaml`](../compose.direct.yaml)。建议先在当前 shell 中声明宿主机路径：

```bash
export PALOPS_BIND_ADDRESS=0.0.0.0
export PALWORLD_SERVICE_ROOT=/srv/palworld
export PALWORLD_SAVE_ROOT=/srv/palworld/Pal/Saved

docker compose -f compose.direct.yaml config --quiet
docker compose -f compose.direct.yaml up -d --build --no-deps palops
```

不要把包含真实宿主机路径的环境文件提交到仓库。如果使用 `.env`，应把它保存在部署机并单独加入本机忽略规则。

Direct Compose 支持以下环境变量：

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `PALOPS_BIND_ADDRESS` | `0.0.0.0` | PalOps 发布端口绑定的宿主机地址；设为 `127.0.0.1` 可关闭局域网访问 |
| `PALEDIT_BIND_ADDRESS` | 无 | 旧名称兼容项；仅在没有设置 `PALOPS_BIND_ADDRESS` 时使用 |
| `PALWORLD_SERVICE_ROOT` | `/srv/palworld` | Palworld 服务根目录，其中应包含服务器 Compose 文件 |
| `PALWORLD_SAVE_ROOT` | `/srv/palworld/Pal/Saved` | Palworld 正式存档根目录，其中应包含 `SaveGames/` |

Compose 中的挂载用途如下：

| 挂载 | 权限 | 用途 |
| --- | --- | --- |
| `palops-state:/state` | 读写 | 保存设置、聊天、指标、本地存档副本和 `.paledit-backups`；这些目录必须位于同一文件系统，才能进行原子替换 |
| `${PALWORLD_SERVICE_ROOT}` | 读写 | 读取和备份服务器 Compose 文件，并在 `palops-backups/` 保存位于 `Saved/` 外的维护安全快照 |
| `${PALWORLD_SAVE_ROOT}` | 只读 | 读取正式服务器存档；该挂载会把服务目录中对应的存档子目录覆盖为只读 |
| `/var/run/docker.sock` | 读写 | 查询容器、执行 RCON、保存世界和执行经过确认的维护操作 |

`PALWORLD_SERVICE_ROOT` 和 `PALWORLD_SAVE_ROOT` 在容器内保持与宿主机相同的绝对路径。这样 Compose 文件中的宿主机路径不会因为进入 PalOps 容器而改变含义。

容器启动后，在“设置”页面填写：

| 设置项 | Direct 模式中的含义 | 推荐值 |
| --- | --- | --- |
| 连接方式 | 选择 `Docker Compose 直连` | `direct` |
| SSH 主机 | Direct 模式不使用该字段 | 保持默认值即可 |
| 公网访问地址 | 玩家从公网连接时使用的域名或 IP，可包含端口；用于延迟采样 | `play.example.com:8211` |
| 存档目录 | 已映射到容器内的正式存档绝对路径 | 与 `PALWORLD_SAVE_ROOT` 相同 |
| Compose 路径 | 已映射到容器内的服务器 Compose 文件 | `${PALWORLD_SERVICE_ROOT}/compose.yaml` |
| Docker 路径 | PalOps Linux 镜像内的 Docker CLI | `/usr/bin/docker` |
| 容器名称 | Palworld 的 Compose 服务名和运行容器名 | `palworld-server` |
| RCON 工具路径 | Palworld 容器内部的 RCON CLI 路径 | `/usr/bin/rcon-cli` |
| RCON 端口 | Palworld 服务器的 RCON TCP 端口 | `25575` |

检查运行状态：

```bash
docker compose -f compose.direct.yaml ps
docker inspect palops --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}'
curl -fsS http://127.0.0.1:18765/api/health
```

更新 PalOps 时只重建 `palops` 服务，不需要停止 Palworld：

```bash
git pull --ff-only
git lfs pull
docker compose -f compose.direct.yaml build --pull palops
docker compose -f compose.direct.yaml up -d --no-deps palops
```

## 网络监听与安全

macOS 启动脚本和 Direct Compose 默认都监听 `0.0.0.0:18765`，同一局域网可以通过部署机 IP 访问：

```text
http://<部署机局域网IP>:18765
```

可用 `PALOPS_BIND_ADDRESS` 覆盖 Direct 模式的监听地址：

```bash
# 只允许部署机本机访问
PALOPS_BIND_ADDRESS=127.0.0.1 docker compose -f compose.direct.yaml up -d --no-deps palops

# 允许所有网卡访问
PALOPS_BIND_ADDRESS=0.0.0.0 docker compose -f compose.direct.yaml up -d --no-deps palops
```

PalOps 当前没有内置登录界面，并且 Docker socket 具有管理宿主机 Docker 的能力。只应在可信局域网中开放；公网访问应放在带认证和 TLS 的反向代理之后，并使用防火墙限制来源。

## 世界数据只读边界

当前网页中的“世界数据”工作区仅用于同步和查看本地快照：

- 玩家资料字段以只读控件显示，不提供保存按钮。
- 背包展示道具名称、内部 ID 和数量，不提供槽位编辑器。
- 备份页面只显示索引、状态和技术路径，不提供恢复或删除入口。
- 从服务器同步仍会更新 PalOps 的本地快照，但不会把本地数据写回正在运行的 Palworld 服务器。

这是界面层限制；后端原有写入接口没有在此次调整中删除或改写。如果将 PalOps 开放给不受信任的网络，仍需通过认证反向代理和网络访问控制保护全部 API，不能把“页面上没有按钮”当作接口级授权。

## 设置参数总表

除连接参数外，“设置”页面还保存以下本机参数：

| 参数 | 作用 | 限制 |
| --- | --- | --- |
| `owner_player_uid` | 标识“我的角色”，用于个人存档、装备和帕鲁视图 | 必须是有效 UUID；应从当前存档身份映射确认，不要按昵称或在线状态猜测 |
| `status_refresh_seconds` | 服务器状态和指标刷新周期 | `5`–`300` 秒，默认 `15` |
| `chat_refresh_seconds` | 聊天记录刷新周期 | `2`–`300` 秒，默认 `5` |
| `connection_method` | 选择 SSH 或 Docker Direct | 仅允许 `ssh`、`direct` |
| `ssh_host` | SSH 主机名或别名 | 只允许字母、数字、点、下划线和连字符；Direct 模式忽略 |
| `public_access_host` | 玩家使用的公网域名或 IP，可包含端口；延迟采样会提取主机并执行 ICMP 往返测试 | 不含协议；端口必须为 `1`–`65535`；留空时不记录延迟 |
| `remote_save_root` | 包含 `SaveGames/` 的服务器存档根目录 | 必须是绝对路径 |
| `remote_compose_path` | Palworld Compose 文件路径 | 必须是绝对路径 |
| `docker_path` | 执行 Docker CLI 的绝对路径 | SSH 模式指远端主机；Direct 模式指 PalOps 容器 |
| `container_name` | Palworld Compose 服务名和容器名 | 只允许字母、数字、点、下划线和连字符 |
| `rcon_path` | Palworld 容器内 RCON CLI 的绝对路径 | 必须是绝对路径 |
| `rcon_port` | RCON TCP 端口 | `1`–`65535` |

这些设置保存在 `.paledit-data/settings.json`；Direct 模式下位于 `palops-state` 卷内。保存设置后可以先执行“测试连接”，不会重启 Palworld。

[返回 README](../README.md)
