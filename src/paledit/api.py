from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .items import get_item, search_items
from .parser import load_character_data
from .save import InvalidSaveError, discover_worlds, sha256

PACKAGE_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = PACKAGE_ROOT / "static"
DEFAULT_SAVE_ROOT = Path.cwd() / "Save"

app = FastAPI(title="PalEdit", version=__version__)
app.mount("/assets", StaticFiles(directory=STATIC_ROOT), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "version": __version__, "platform": "macOS"}


@app.get("/api/items")
def items(q: str = "", limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    return search_items(q, limit)


@app.get("/api/items/{item_id}")
def item(item_id: str) -> dict[str, object]:
    result = get_item(item_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未知道具 ID：{item_id}")
    return result


@app.get("/api/worlds")
def worlds(root: str = Query(default=str(DEFAULT_SAVE_ROOT))) -> dict[str, object]:
    try:
        items = discover_worlds(Path(root))
    except InvalidSaveError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"root": str(Path(root).expanduser().resolve()), "worlds": [item.dump() for item in items]}


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
        "level_sha256": sha256(level),
        "character_count": parsed["character_count"],
        "world_property_count": parsed["world_property_count"],
        "write_enabled": False,
        "compatibility": "Palworld 1.0 PlM/Oodle read-only",
    }
