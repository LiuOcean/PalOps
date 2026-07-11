from __future__ import annotations

import hashlib
from pathlib import Path

from .models import SaveFileInfo, WorldInfo

MAGIC_OFFSET = 8


class InvalidSaveError(ValueError):
    pass


def inspect_save(path: Path) -> SaveFileInfo:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise InvalidSaveError(f"存档文件不存在：{path}")
    header = path.read_bytes()[:16]
    if len(header) < 12:
        raise InvalidSaveError(f"存档头不完整：{path}")
    magic_bytes = header[MAGIC_OFFSET : MAGIC_OFFSET + 3]
    magic = magic_bytes.decode("ascii", errors="replace")
    format_name = {"PlM": "oodle", "PlZ": "zlib"}.get(magic, "unknown")
    save_type = header[11] if magic in {"PlM", "PlZ"} else None
    return SaveFileInfo(
        name=path.name,
        path=str(path),
        size=path.stat().st_size,
        magic=magic,
        format=format_name,
        save_type=save_type,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_worlds(save_root: Path) -> list[WorldInfo]:
    save_root = save_root.expanduser().resolve()
    base = save_root / "SaveGames" / "0"
    if not base.is_dir():
        raise InvalidSaveError(f"没有找到服务器世界目录：{base}")

    worlds: list[WorldInfo] = []
    for world_dir in sorted(path for path in base.iterdir() if path.is_dir()):
        level_path = world_dir / "Level.sav"
        if not level_path.is_file():
            continue
        meta_path = world_dir / "LevelMeta.sav"
        players_dir = world_dir / "Players"
        backups_dir = world_dir / "backup" / "world"
        worlds.append(
            WorldInfo(
                world_id=world_dir.name,
                path=str(world_dir),
                player_files=len(list(players_dir.glob("*.sav"))) if players_dir.is_dir() else 0,
                backup_sets=len([p for p in backups_dir.iterdir() if p.is_dir()]) if backups_dir.is_dir() else 0,
                level=inspect_save(level_path),
                level_meta=inspect_save(meta_path) if meta_path.is_file() else None,
            )
        )
    return worlds

