from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .backups import delete_backup, list_backups, prepare_backup_restore, restore_backup
from .items import get_item, search_items
from .map import get_map_config
from .pals import search_pals
from .parser import PARSER_REVISION, invalidate_world_snapshot, load_character_data, parser_capabilities
from .remote import (
    get_server_config, get_server_metrics, get_server_status, list_online_players, prepare_server_restart,
    pull_latest_save, restart_server, run_server_action, update_server_config,
)
from .save import InvalidSaveError, discover_worlds
from .skills import search_skills
from .world import (
    list_guilds, list_storage_containers, list_users, search_world, update_inventory_slot, update_user,
    world_snapshot_payload,
)

PACKAGE_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = PACKAGE_ROOT / "static"
DEFAULT_SAVE_ROOT = Path.cwd() / "Save"
DEFAULT_SYNC_BACKUP_ROOT = Path.cwd() / ".paledit-backups"

app = FastAPI(title="PalEdit", version=__version__)
app.mount("/assets", StaticFiles(directory=STATIC_ROOT), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "version": __version__, "platform": "macOS"}


@app.get("/api/items")
def items(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: list[str] = Query(default=[]),
) -> dict[str, object]:
    return search_items(q, limit, offset, category)


@app.get("/api/items/{item_id}")
def item(item_id: str) -> dict[str, object]:
    result = get_item(item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未知道具 ID：{item_id}")
    return result


@app.get("/api/pals")
def pals(q: str = "", limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    return search_pals(q, limit)


@app.get("/api/skills")
def skills(q: str = "", limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    return search_skills(q, limit)


@app.get("/api/worlds")
def worlds(root: str = Query(default=str(DEFAULT_SAVE_ROOT))) -> dict[str, object]:
    try:
        items = discover_worlds(Path(root))
    except InvalidSaveError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"root": str(Path(root).expanduser().resolve()), "worlds": [item.dump() for item in items]}


@app.post("/api/save/pull")
def pull_save() -> dict[str, object]:
    try:
        result = pull_latest_save(DEFAULT_SAVE_ROOT)
        invalidate_world_snapshot()
        return result
    except (InvalidSaveError, OSError, RuntimeError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/backups")
def backups() -> dict[str, object]:
    try:
        return list_backups(DEFAULT_SAVE_ROOT, DEFAULT_SYNC_BACKUP_ROOT)
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"读取本地备份失败：{error}") from error


@app.post("/api/backups/restore/prepare")
def backup_restore_prepare(payload: dict = Body(...)) -> dict[str, object]:
    try:
        return prepare_backup_restore(
            str(payload["backup_id"]), str(payload["world_id"]), DEFAULT_SAVE_ROOT, DEFAULT_SYNC_BACKUP_ROOT,
        )
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"检查备份失败：{error}") from error


@app.post("/api/backups/restore")
def backup_restore(payload: dict = Body(...)) -> dict[str, object]:
    try:
        if payload.get("confirmed") is not True:
            raise ValueError("请完成备份恢复确认")
        result = restore_backup(
            str(payload["backup_id"]), str(payload["world_id"]), str(payload["expected_sha256"]),
            DEFAULT_SAVE_ROOT, DEFAULT_SYNC_BACKUP_ROOT,
        )
        invalidate_world_snapshot()
        return result
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"恢复备份失败：{error}") from error


@app.delete("/api/backups/{backup_id}")
def backup_delete(backup_id: str, payload: dict = Body(...)) -> dict[str, object]:
    try:
        if payload.get("confirmed") is not True:
            raise ValueError("请完成备份删除确认")
        return delete_backup(
            backup_id, str(payload["expected_created_at"]), int(payload["expected_size_bytes"]),
            DEFAULT_SAVE_ROOT, DEFAULT_SYNC_BACKUP_ROOT,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"删除备份失败：{error}") from error


@app.get("/api/server/status")
def server_status() -> dict[str, object]:
    try:
        return get_server_status()
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/server/players")
def server_players() -> dict[str, object]:
    try:
        players = list_online_players()
        return {"players": players, "count": len(players)}
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/server/metrics")
def server_metrics() -> dict[str, int | float | None]:
    try:
        return get_server_metrics()
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/server/actions")
def server_action(payload: dict = Body(...)) -> dict[str, object]:
    try:
        if payload.get("confirmed") is not True:
            raise ValueError("请先确认本次服务器操作")
        return run_server_action(
            str(payload.get("action", "")),
            message=payload.get("message"),
            seconds=payload.get("seconds"),
            player_uid=payload.get("player_uid"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/server/config")
def server_config() -> dict[str, object]:
    try:
        return get_server_config()
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.put("/api/server/config")
def save_server_config(payload: dict = Body(...)) -> dict[str, object]:
    try:
        return update_server_config(dict(payload.get("updates") or {}), str(payload.get("expected_revision") or ""))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/api/server/restart/prepare")
def server_restart_prepare() -> dict[str, object]:
    return prepare_server_restart()


@app.post("/api/server/restart")
def server_restart(payload: dict = Body(...)) -> dict[str, object]:
    try:
        if payload.get("confirmed") is not True:
            raise ValueError("请完成第二次重启确认")
        return restart_server(str(payload.get("confirmation_token") or ""))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/world/inspect")
def inspect_world(path: str) -> dict[str, object]:
    world = Path(path).expanduser().resolve()
    level = world / "Level.sav"
    try:
        parsed = load_character_data(level)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"1.0 存档解析失败：{error}") from error
    return {
        "world_id": world.name,
        "level_sha256": parsed["level_sha256"],
        "character_count": parsed["character_count"],
        "world_property_count": parsed["world_property_count"],
        "parser_revision": PARSER_REVISION,
        "capabilities": parser_capabilities(),
        "warnings": ["MapObject 使用原始字节扫描回退；未知结构保持不透明。"],
        "write_enabled": True,
        "compatibility": "Palworld 1.0 PlM 读取 / Pal 支持的 PlZ 安全写入",
    }


@app.get("/api/world/snapshot")
def world_snapshot(path: str) -> dict[str, object]:
    try:
        return world_snapshot_payload(Path(path))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"读取世界快照失败：{error}") from error


@app.get("/api/world/users")
def users(path: str) -> dict[str, object]:
    try:
        return list_users(Path(path))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"读取用户失败：{error}") from error


@app.get("/api/world/containers")
def containers(path: str) -> dict[str, object]:
    try:
        return list_storage_containers(Path(path))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"读取箱子失败：{error}") from error


@app.get("/api/world/search")
def world_search(
    path: str,
    q: str = Query(min_length=1),
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict[str, object]:
    try:
        return search_world(Path(path), q, limit)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"全局搜索失败：{error}") from error


@app.get("/api/world/guilds")
def guilds(path: str) -> dict[str, object]:
    try:
        return list_guilds(Path(path))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"读取公会失败：{error}") from error


@app.get("/api/world/map")
def world_map() -> dict[str, object]:
    try:
        return get_map_config()
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"读取地图数据失败：{error}") from error


@app.patch("/api/world/users/{player_uid}")
def patch_user(player_uid: str, path: str, payload: dict = Body(...)) -> dict[str, object]:
    try:
        expected = str(payload.pop("expected_sha256"))
        expected_player = payload.pop("expected_player_sha256", None)
        return update_user(Path(path), player_uid, payload, expected, expected_player)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.patch("/api/world/users/{player_uid}/inventory")
def patch_inventory(player_uid: str, path: str, payload: dict = Body(...)) -> dict[str, object]:
    try:
        return update_inventory_slot(
            Path(path), player_uid, str(payload["category"]), int(payload["slot_index"]),
            str(payload["item_id"]), int(payload["count"]), str(payload["expected_sha256"]),
        )
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
