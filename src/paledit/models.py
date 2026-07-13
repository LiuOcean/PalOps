from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SaveFileInfo:
    name: str
    path: str
    size: int
    modified_at: float
    magic: str
    format: str
    save_type: int | None

    def dump(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WorldInfo:
    world_id: str
    path: str
    player_files: int
    backup_sets: int
    level: SaveFileInfo
    level_meta: SaveFileInfo | None

    def dump(self) -> dict[str, object]:
        result = asdict(self)
        result["level"] = self.level.dump()
        result["level_meta"] = self.level_meta.dump() if self.level_meta else None
        return result


def relative_display(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
