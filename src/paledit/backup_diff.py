from __future__ import annotations

import hashlib
import json
import multiprocessing
import shutil
import sqlite3
import tarfile
import tempfile
import threading
import time
import uuid
import zlib
from collections import OrderedDict
from concurrent.futures import Future, ProcessPoolExecutor
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from .backups import list_backups
from .parser import PARSER_REVISION
from .save import sha256
from .world import world_snapshot_payload


DEFAULT_DIFF_DB = Path.cwd() / ".paledit-data" / "backup-diff.sqlite3"
PROJECTION_REVISION = "backup-diff-v5"
MAX_ARCHIVE_FILE_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_WORLD_BYTES = 2 * 1024 * 1024 * 1024
MAX_JOBS = 20
CATEGORY_ORDER = ("players", "pals", "containers", "guilds", "world", "files")
CATEGORY_LABELS = {
    "players": "玩家",
    "pals": "帕鲁",
    "containers": "储物箱",
    "guilds": "公会",
    "world": "世界数据",
    "files": "文件",
}
ENTITY_TYPE_LABELS = {
    "player": "玩家",
    "inventory_slot": "玩家背包",
    "pal": "帕鲁",
    "container": "储物箱",
    "container_slot": "储物箱槽位",
    "guild": "公会",
    "guild_member": "公会成员",
    "base": "公会据点",
    "summary": "世界摘要",
    "file": "文件",
}


def _safe_world_id(world_id: str) -> str:
    value = world_id.strip()
    if not value or value in {".", ".."} or Path(value).name != value:
        raise ValueError("无效的世界 ID")
    return value


def _backup_rows(save_root: Path, sync_backup_root: Path, game_backup_root: Path | None) -> list[dict[str, object]]:
    return list_backups(save_root, sync_backup_root, game_backup_root)["backups"]


def _find_backup(
    backup_id: str,
    save_root: Path,
    sync_backup_root: Path,
    game_backup_root: Path | None,
) -> dict[str, object]:
    for row in _backup_rows(save_root, sync_backup_root, game_backup_root):
        if row["backup_id"] == backup_id:
            return row
    raise ValueError("备份不存在或已被移动，请重新扫描")


def validate_backup_pair(
    base_backup_id: str,
    target_backup_id: str,
    world_id: str,
    save_root: Path,
    sync_backup_root: Path,
    game_backup_root: Path | None = None,
) -> dict[str, object]:
    world_id = _safe_world_id(world_id)
    if base_backup_id == target_backup_id:
        raise ValueError("请选择两个不同的备份版本")
    base = _find_backup(base_backup_id, save_root, sync_backup_root, game_backup_root)
    target = _find_backup(target_backup_id, save_root, sync_backup_root, game_backup_root)
    for label, backup in (("基准版本", base), ("对比版本", target)):
        if not backup["has_level_save"]:
            raise ValueError(f"{label}不包含可比较的 Level.sav")
        if world_id not in backup["world_ids"]:
            raise ValueError(f"{label}不包含所选世界")
    return {"world_id": world_id, "base": base, "target": target}


def _has_symlink(root: Path) -> bool:
    return any(path.is_symlink() for path in root.rglob("*"))


def _archive_world_prefix(archive: tarfile.TarFile, world_id: str) -> tuple[str, ...]:
    candidates: list[tuple[str, ...]] = []
    for member in archive.getmembers():
        if not member.isfile():
            continue
        parts = tuple(part for part in PurePosixPath(member.name).parts if part not in {"", "."})
        if ".." in parts:
            continue
        for index in range(max(0, len(parts) - 3)):
            if (
                parts[index:index + 2] == ("SaveGames", "0")
                and index + 3 < len(parts)
                and parts[index + 2] == world_id
                and parts[index + 3] == "Level.sav"
            ):
                candidates.append(parts[:index + 3])
    if not candidates:
        raise ValueError("压缩备份中没有找到所选世界的 Level.sav")
    return min(candidates, key=len)


def _extract_archive_world(archive_path: Path, world_id: str, destination: Path) -> Path:
    total_size = 0
    with tarfile.open(archive_path, mode="r:gz") as archive:
        prefix = _archive_world_prefix(archive, world_id)
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = tuple(part for part in PurePosixPath(member.name).parts if part not in {"", "."})
            if ".." in parts or parts[:len(prefix)] != prefix:
                continue
            relative_parts = parts[len(prefix):]
            if not relative_parts:
                continue
            if member.size < 0 or member.size > MAX_ARCHIVE_FILE_BYTES:
                raise ValueError("压缩备份包含异常大小的文件，已拒绝比较")
            total_size += member.size
            if total_size > MAX_ARCHIVE_WORLD_BYTES:
                raise ValueError("压缩备份展开后超过安全限制，已拒绝比较")
            target = destination.joinpath(*relative_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("压缩备份中的文件无法读取")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    if not (destination / "Level.sav").is_file():
        raise ValueError("压缩备份展开后缺少 Level.sav")
    return destination


@contextmanager
def resolved_backup_world(backup: dict[str, object], world_id: str) -> Iterator[Path]:
    path = Path(str(backup["path"])).expanduser().resolve()
    if backup["is_archive"]:
        with tempfile.TemporaryDirectory(prefix="palops-backup-diff-") as temporary:
            yield _extract_archive_world(path, world_id, Path(temporary) / world_id)
        return
    world_path = path / "SaveGames" / "0" / world_id if backup["source"] == "sync" else path
    if not world_path.is_dir() or world_path.is_symlink() or _has_symlink(world_path):
        raise ValueError("备份世界目录无效或包含符号链接，已拒绝比较")
    if not (world_path / "Level.sav").is_file():
        raise ValueError("备份世界目录缺少 Level.sav")
    yield world_path


def _manifest(world_path: Path) -> list[dict[str, object]]:
    ignored = {"backup", "PalEdit-Backup", "PalEdit-Remote-Backup"}
    rows: list[dict[str, object]] = []
    for path in sorted(world_path.rglob("*")):
        relative = path.relative_to(world_path)
        if any(part in ignored for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("备份世界目录包含符号链接，已拒绝比较")
        if not path.is_file():
            continue
        rows.append({
            "path": relative.as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })
    return rows


def _manifest_fingerprint(manifest: list[dict[str, object]]) -> str:
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _plain(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_plain(item) for item in value]
    return str(value)


def _display(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, list):
        return "、".join(_display(item) for item in value) if value else "—"
    if isinstance(value, dict):
        return "；".join(f"{key}：{_display(item)}" for key, item in value.items()) if value else "—"
    return str(value)


def build_projection(world_path: Path, manifest: list[dict[str, object]] | None = None) -> dict[str, object]:
    snapshot = world_snapshot_payload(world_path)
    records: dict[str, dict[str, object]] = {}

    def add_record(
        category: str,
        entity_type: str,
        entity_id: str,
        label: str,
        fields: dict[str, object],
        *,
        important_fields: tuple[str, ...] = (),
        important_default: bool = False,
        group_id: str | None = None,
        group_label: str | None = None,
        group_entity_type: str | None = None,
    ) -> None:
        records[f"{category}:{entity_type}:{entity_id}"] = {
            "category": category,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_label": label or entity_id,
            "fields": {key: _plain(value) for key, value in fields.items()},
            "important_fields": list(important_fields),
            "important_default": important_default,
            "group_id": group_id or entity_id,
            "group_label": group_label or label or entity_id,
            "group_entity_type": group_entity_type or entity_type,
        }

    summary = dict(snapshot["summary"])
    add_record(
        "world", "summary", str(snapshot["world_id"]), "世界摘要",
        {
            "角色数量": summary.get("character_count", 0),
            "玩家数量": summary.get("user_count", 0),
            "储物箱数量": summary.get("container_count", 0),
            "公会数量": summary.get("guild_count", 0),
            "基地数量": summary.get("base_count", 0),
        },
        important_fields=("玩家数量", "储物箱数量", "公会数量", "基地数量"),
    )

    for user in list(snapshot["users"]):
        uid = str(user["player_uid"])
        name = str(user.get("nickname") or f"玩家 · {uid[-6:]}")
        add_record(
            "players", "player", uid, name,
            {
                "昵称": user.get("nickname", ""),
                "等级": user.get("level", 1),
                "经验值": user.get("experience", 0),
                "生命值": user.get("hp", 0),
                "护盾值": user.get("shield_hp", 0),
                "饱食度": user.get("satiety", 0),
                "未分配属性点": user.get("unused_status_points", 0),
                "科技点": user.get("technology_points", 0),
                "古代科技点": user.get("boss_technology_points", 0),
                "属性加点": user.get("status_points", {}),
                "拥有帕鲁": user.get("pal_count", 0),
            },
            important_fields=("昵称", "等级", "科技点", "古代科技点", "拥有帕鲁"),
            important_default=True,
        )
        for inventory_name, slots in dict(user.get("inventories") or {}).items():
            for slot in list(slots):
                if slot.get("item_id") == "None" or int(slot.get("count") or 0) <= 0:
                    continue
                slot_index = int(slot["slot_index"])
                add_record(
                    "players", "inventory_slot", f"{uid}:{inventory_name}:{slot_index}",
                    f"{name} · {inventory_name} · 槽位 {slot_index + 1}",
                    {"道具": slot.get("name_zh") or slot.get("item_id"), "数量": slot.get("count", 0)},
                    important_fields=("道具", "数量"),
                    important_default=True,
                    group_id=uid,
                    group_label=name,
                    group_entity_type="player",
                )
        for pal in list(user.get("pals") or []):
            pal_id = str(pal["instance_id"])
            pal_name = str(pal.get("nickname") or pal.get("name_zh") or pal.get("character_id") or pal_id)
            add_record(
                "pals", "pal", pal_id, f"{pal_name} · {name}",
                {
                    "帕鲁": pal.get("name_zh") or pal.get("character_id"),
                    "昵称": pal.get("nickname", ""),
                    "所属玩家": name,
                    "所属玩家 UID": uid,
                    "等级": pal.get("level", 1),
                    "经验值": pal.get("experience", 0),
                    "当前生命值": pal.get("hp", 0),
                    "性别": pal.get("gender", ""),
                    "Boss": pal.get("is_boss", False),
                    "闪光": pal.get("is_lucky", False),
                    "塔主": pal.get("is_tower", False),
                    "所在位置": pal.get("location_type", "其他帕鲁容器"),
                    "容器标识": pal.get("container_id", ""),
                    "槽位": int(pal.get("slot_index", -1)) + 1,
                    "浓缩等级": pal.get("condensation_rank", 1),
                    "强化": pal.get("rank_boosts", {}),
                    "天赋": pal.get("talents", {}),
                    "被动技能": [skill.get("name_zh") or skill.get("skill_id") for skill in pal.get("passive_skills", [])],
                },
                important_fields=(
                    "帕鲁", "昵称", "所属玩家", "所属玩家 UID", "等级", "所在位置",
                    "容器标识", "Boss", "闪光", "塔主", "浓缩等级", "强化", "天赋", "被动技能",
                ),
                important_default=True,
            )

    for container in list(snapshot["containers"]):
        container_id = str(container["container_id"])
        label = str(container.get("label") or container.get("type_name") or f"储物箱 · {container_id[-6:]}")
        add_record(
            "containers", "container", container_id, label,
            {
                "名称": container.get("label", ""),
                "类型": container.get("type_name", ""),
                "容量": container.get("slot_capacity", 0),
                "已用槽位": container.get("occupied_slots", 0),
                "物品总数": container.get("total_items", 0),
            },
            important_fields=("名称", "类型", "容量", "已用槽位", "物品总数"),
            important_default=True,
        )
        for slot in list(container.get("slots") or []):
            if slot.get("item_id") == "None" or int(slot.get("count") or 0) <= 0:
                continue
            slot_index = int(slot["slot_index"])
            add_record(
                "containers", "container_slot", f"{container_id}:{slot_index}",
                f"{label} · 槽位 {slot_index + 1}",
                {"道具": slot.get("name_zh") or slot.get("item_id"), "数量": slot.get("count", 0)},
                important_fields=("道具", "数量"),
                important_default=True,
                group_id=container_id,
                group_label=label,
                group_entity_type="container",
            )

    for guild in list(snapshot["guilds"]):
        guild_id = str(guild["guild_id"])
        guild_name = str(guild.get("display_name") or guild.get("name") or f"公会 · {guild_id[-6:]}")
        add_record(
            "guilds", "guild", guild_id, guild_name,
            {
                "公会名称": guild_name,
                "管理员": guild.get("admin_player_uid", ""),
                "成员数量": guild.get("member_count", 0),
                "公会等级": guild.get("base_camp_level", 0),
                "基地数量": guild.get("base_count", 0),
            },
            important_fields=("公会名称", "管理员", "成员数量", "公会等级", "基地数量"),
            important_default=True,
        )
        for member in list(guild.get("players") or []):
            member_uid = str(member["player_uid"])
            add_record(
                "guilds", "guild_member", f"{guild_id}:{member_uid}",
                f"{guild_name} · {member.get('nickname') or member_uid[-6:]}",
                {"成员": member.get("nickname") or member_uid[-6:], "最后在线": member.get("last_online")},
                important_fields=("成员",),
                important_default=True,
                group_id=guild_id,
                group_label=guild_name,
                group_entity_type="guild",
            )
        for base in list(guild.get("base_camps") or []):
            base_id = str(base["base_id"])
            add_record(
                "guilds", "base", base_id,
                f"{guild_name} · 基地 {base_id[-6:]}",
                {"状态": base.get("state"), "范围": base.get("area_range"), "坐标": base.get("location")},
                important_fields=("状态", "范围"),
                important_default=True,
                group_id=guild_id,
                group_label=guild_name,
                group_entity_type="guild",
            )

    for file in manifest or _manifest(world_path):
        relative = str(file["path"])
        add_record(
            "files", "file", relative, relative,
            {"大小": file["size"], "SHA-256": file["sha256"]},
            important_default=False,
        )

    return {
        "world_id": snapshot["world_id"],
        "level_sha256": snapshot["level_sha256"],
        "parser_revision": PARSER_REVISION,
        "projection_revision": PROJECTION_REVISION,
        "records": records,
    }


def diff_projections(base: dict[str, object], target: dict[str, object]) -> dict[str, object]:
    base_records = dict(base["records"])
    target_records = dict(target["records"])
    changes: list[dict[str, object]] = []

    def append_change(
        key: str,
        record: dict[str, object],
        change_type: str,
        field: str,
        before: object,
        after: object,
        important: bool,
    ) -> None:
        change_key = f"{key}\0{change_type}\0{field}"
        changes.append({
            "change_id": hashlib.sha1(change_key.encode()).hexdigest(),
            "category": record["category"],
            "category_label": CATEGORY_LABELS[str(record["category"])],
            "entity_type": record["entity_type"],
            "entity_id": record["entity_id"],
            "entity_label": record["entity_label"],
            "group_id": record.get("group_id", record["entity_id"]),
            "group_label": record.get("group_label", record["entity_label"]),
            "group_entity_type": record.get("group_entity_type", record["entity_type"]),
            "field": field,
            "change_type": change_type,
            "change_type_label": {"added": "新增", "modified": "修改", "removed": "删除"}[change_type],
            "before": _display(before),
            "after": _display(after),
            "important": important,
        })

    for key in sorted(set(base_records) | set(target_records)):
        before_record = base_records.get(key)
        after_record = target_records.get(key)
        if before_record is None:
            append_change(key, after_record, "added", "记录", None, "已存在", bool(after_record["important_default"]))
            continue
        if after_record is None:
            append_change(key, before_record, "removed", "记录", "已存在", None, bool(before_record["important_default"]))
            continue
        before_fields = dict(before_record["fields"])
        after_fields = dict(after_record["fields"])
        important_fields = set(before_record["important_fields"]) | set(after_record["important_fields"])
        for field in sorted(set(before_fields) | set(after_fields)):
            before = before_fields.get(field)
            after = after_fields.get(field)
            if before == after:
                continue
            append_change(key, after_record, "modified", field, before, after, field in important_fields)

    category_index = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    type_index = {"added": 0, "modified": 1, "removed": 2}
    changes.sort(key=lambda row: (
        category_index[str(row["category"])], str(row["entity_label"]),
        type_index[str(row["change_type"])], str(row["field"]),
    ))
    field_summary = {
        change_type: sum(row["change_type"] == change_type for row in changes)
        for change_type in ("added", "modified", "removed")
    }
    field_summary["total"] = len(changes)
    field_summary["important"] = sum(bool(row["important"]) for row in changes)
    groups = group_changes(changes)
    summary = {
        change_type: sum(group["change_type"] == change_type for group in groups)
        for change_type in ("added", "modified", "removed")
    }
    summary["total"] = len(groups)
    summary["important"] = sum(bool(group["important"]) for group in groups)
    summary["field_total"] = len(changes)
    categories = []
    for category in CATEGORY_ORDER:
        category_rows = [row for row in changes if row["category"] == category]
        category_groups = [group for group in groups if group["category"] == category]
        categories.append({
            "key": category,
            "label": CATEGORY_LABELS[category],
            "total": len(category_groups),
            "field_total": len(category_rows),
            "added": sum(group["change_type"] == "added" for group in category_groups),
            "modified": sum(group["change_type"] == "modified" for group in category_groups),
            "removed": sum(group["change_type"] == "removed" for group in category_groups),
        })
    active_categories = sorted(
        (category for category in categories if category["total"]),
        key=lambda category: int(category["total"]),
        reverse=True,
    )
    dominant = "和".join(str(category["label"]) for category in active_categories[:2])
    headline = f"变化主要集中在{dominant}" if dominant else "两个版本没有可见的数据变化"
    overview = {
        "headline": headline,
        "affected_entities": len(groups),
        "field_total": len(changes),
        "active_categories": len(active_categories),
        "field_summary": field_summary,
    }
    return {"summary": summary, "overview": overview, "categories": categories, "changes": changes}


def group_changes(changes: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: OrderedDict[str, dict[str, object]] = OrderedDict()
    for change in changes:
        group_key = "\0".join(str(change[key]) for key in ("category", "group_id"))
        group = grouped.get(group_key)
        if group is None:
            group = {
                "group_id": hashlib.sha1(group_key.encode()).hexdigest(),
                "category": change["category"],
                "category_label": change["category_label"],
                "entity_type": change["group_entity_type"],
                "entity_type_label": ENTITY_TYPE_LABELS.get(str(change["group_entity_type"]), "数据对象"),
                "entity_id": change["group_id"],
                "entity_label": change["group_label"],
                "change_type": change["change_type"],
                "change_type_label": change["change_type_label"],
                "important": False,
                "field_count": 0,
                "changes": [],
                "_change_types": set(),
                "_has_child_change": False,
                "_root_change_type": None,
            }
            grouped[group_key] = group
        group["changes"].append(change)
        group["field_count"] = int(group["field_count"]) + 1
        group["important"] = bool(group["important"]) or bool(change["important"])
        group["_change_types"].add(change["change_type"])
        if change["entity_id"] == change["group_id"]:
            group["_root_change_type"] = change["change_type"]
        else:
            group["_has_child_change"] = True
    for group in grouped.values():
        root_change_type = group.pop("_root_change_type")
        change_types = group.pop("_change_types")
        has_child_change = group.pop("_has_child_change")
        if root_change_type in {"added", "removed"}:
            group["change_type"] = root_change_type
        elif has_child_change or len(change_types) > 1 or "modified" in change_types:
            group["change_type"] = "modified"
            group["change_type_label"] = "修改"
        group["change_type_label"] = {"added": "新增", "modified": "修改", "removed": "删除"}[str(group["change_type"])]
    return list(grouped.values())


def _cache_connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_diffs (
            cache_key TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL,
            payload BLOB NOT NULL
        )
        """
    )
    return connection


def _read_cache(path: Path, cache_key: str) -> dict[str, object] | None:
    with _cache_connect(path) as connection:
        row = connection.execute("SELECT payload FROM backup_diffs WHERE cache_key = ?", (cache_key,)).fetchone()
    if row is None:
        return None
    return json.loads(zlib.decompress(row[0]).decode())


def _write_cache(path: Path, cache_key: str, payload: dict[str, object]) -> None:
    encoded = zlib.compress(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(), level=6)
    with _cache_connect(path) as connection:
        connection.execute(
            "INSERT OR REPLACE INTO backup_diffs(cache_key, created_at, payload) VALUES (?, ?, ?)",
            (cache_key, int(time.time()), encoded),
        )
        connection.execute(
            "DELETE FROM backup_diffs WHERE cache_key IN (SELECT cache_key FROM backup_diffs ORDER BY created_at DESC LIMIT -1 OFFSET 40)"
        )


def compute_backup_diff(
    base_backup_id: str,
    target_backup_id: str,
    world_id: str,
    save_root: str,
    sync_backup_root: str,
    game_backup_root: str | None,
    cache_db: str,
) -> dict[str, object]:
    roots = (Path(save_root), Path(sync_backup_root), Path(game_backup_root) if game_backup_root else None)
    pair = validate_backup_pair(base_backup_id, target_backup_id, world_id, *roots)
    with ExitStack() as stack:
        base_world = stack.enter_context(resolved_backup_world(dict(pair["base"]), str(pair["world_id"])))
        target_world = stack.enter_context(resolved_backup_world(dict(pair["target"]), str(pair["world_id"])))
        base_manifest = _manifest(base_world)
        target_manifest = _manifest(target_world)
        base_fingerprint = _manifest_fingerprint(base_manifest)
        target_fingerprint = _manifest_fingerprint(target_manifest)
        cache_key = hashlib.sha256(
            f"{base_fingerprint}\0{target_fingerprint}\0{PARSER_REVISION}\0{PROJECTION_REVISION}".encode()
        ).hexdigest()
        cached = _read_cache(Path(cache_db), cache_key)
        if cached is not None:
            cached["cached"] = True
            return cached
        base_projection = build_projection(base_world, base_manifest)
        target_projection = build_projection(target_world, target_manifest)
        result = diff_projections(base_projection, target_projection)
        result.update({
            "cache_key": cache_key,
            "cached": False,
            "world_id": pair["world_id"],
            "parser_revision": PARSER_REVISION,
            "projection_revision": PROJECTION_REVISION,
            "versions": {
                "base": {
                    "backup_id": pair["base"]["backup_id"],
                    "name": pair["base"]["name"],
                    "source_label": pair["base"]["source_label"],
                    "created_at": pair["base"]["created_at"],
                    "fingerprint": base_fingerprint,
                    "level_sha256": base_projection["level_sha256"],
                },
                "target": {
                    "backup_id": pair["target"]["backup_id"],
                    "name": pair["target"]["name"],
                    "source_label": pair["target"]["source_label"],
                    "created_at": pair["target"]["created_at"],
                    "fingerprint": target_fingerprint,
                    "level_sha256": target_projection["level_sha256"],
                },
            },
        })
        _write_cache(Path(cache_db), cache_key, result)
        return result


class BackupDiffService:
    def __init__(
        self,
        *,
        worker: Callable[..., dict[str, object]] = compute_backup_diff,
        executor_factory: Callable[[], ProcessPoolExecutor] | None = None,
    ) -> None:
        self._worker = worker
        self._executor_factory = executor_factory or self._new_executor
        self._executor: ProcessPoolExecutor | None = None
        self._jobs: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _new_executor() -> ProcessPoolExecutor:
        return ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            max_tasks_per_child=8,
        )

    def start(
        self,
        base_backup_id: str,
        target_backup_id: str,
        world_id: str,
        save_root: Path,
        sync_backup_root: Path,
        game_backup_root: Path | None,
        cache_db: Path,
    ) -> dict[str, object]:
        pair = validate_backup_pair(
            base_backup_id, target_backup_id, world_id, save_root, sync_backup_root, game_backup_root,
        )
        with self._lock:
            if self._executor is None:
                self._executor = self._executor_factory()
            job_id = uuid.uuid4().hex
            future = self._executor.submit(
                self._worker,
                base_backup_id,
                target_backup_id,
                str(pair["world_id"]),
                str(save_root),
                str(sync_backup_root),
                str(game_backup_root) if game_backup_root else None,
                str(cache_db),
            )
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "progress": 15,
                "message": "正在解析两个版本并生成语义差异…",
                "created_at": int(time.time()),
                "future": future,
                "result": None,
                "error": None,
                "selection": {
                    "world_id": pair["world_id"],
                    "base_backup_id": base_backup_id,
                    "target_backup_id": target_backup_id,
                },
            }
            future.add_done_callback(lambda completed, current_job_id=job_id: self._complete(current_job_id, completed))
            self._prune()
            return self.status(job_id)

    def _complete(self, job_id: str, future: Future) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            try:
                result = future.result()
            except Exception as error:  # Worker errors are presented as a read-only comparison failure.
                job.update({"status": "error", "progress": 100, "message": "版本比较失败", "error": str(error)})
            else:
                job.update({
                    "status": "ready",
                    "progress": 100,
                    "message": "版本差异已生成",
                    "result": result,
                })

    def _prune(self) -> None:
        while len(self._jobs) > MAX_JOBS:
            oldest_id, oldest = next(iter(self._jobs.items()))
            if oldest["status"] == "running":
                break
            self._jobs.pop(oldest_id, None)

    def _job(self, job_id: str) -> dict[str, object]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError("比较任务不存在或已过期")
            return job

    def status(self, job_id: str) -> dict[str, object]:
        job = self._job(job_id)
        payload = {
            "job_id": job["job_id"],
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "error": job["error"],
            "selection": job["selection"],
        }
        if job["status"] == "ready":
            result = dict(job["result"])
            payload.update({
                "cached": result["cached"],
                "world_id": result["world_id"],
                "versions": result["versions"],
                "summary": result["summary"],
                "overview": result["overview"],
                "categories": result["categories"],
                "parser_revision": result["parser_revision"],
                "projection_revision": result["projection_revision"],
            })
        return payload

    def changes(
        self,
        job_id: str,
        *,
        category: str = "",
        change_type: str = "",
        query: str = "",
        important_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, object]:
        job = self._job(job_id)
        if job["status"] != "ready":
            raise ValueError("版本差异尚未生成完成")
        rows = list(dict(job["result"])["changes"])
        if category:
            rows = [row for row in rows if row["category"] == category]
        if change_type:
            rows = [row for row in rows if row["change_type"] == change_type]
        if important_only:
            rows = [row for row in rows if row["important"]]
        needle = query.strip().casefold()
        if needle:
            rows = [row for row in rows if needle in " ".join(str(value) for value in (
                row["category_label"], row["entity_label"], row["entity_id"], row["field"],
                row["before"], row["after"], row["change_type_label"],
            )).casefold()]
        page = rows[offset:offset + limit]
        next_offset = offset + len(page)
        return {
            "job_id": job_id,
            "count": len(rows),
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset if next_offset < len(rows) else None,
            "changes": page,
        }

    def groups(
        self,
        job_id: str,
        *,
        category: str = "",
        change_type: str = "",
        query: str = "",
        important_only: bool = False,
        offset: int = 0,
        limit: int = 25,
    ) -> dict[str, object]:
        job = self._job(job_id)
        if job["status"] != "ready":
            raise ValueError("版本差异尚未生成完成")
        rows = list(dict(job["result"])["changes"])
        if category:
            rows = [row for row in rows if row["category"] == category]
        if change_type:
            rows = [row for row in rows if row["change_type"] == change_type]
        if important_only:
            rows = [row for row in rows if row["important"]]
        needle = query.strip().casefold()
        if needle:
            rows = [row for row in rows if needle in " ".join(str(value) for value in (
                row["category_label"], row["entity_label"], row["entity_id"], row["field"],
                row["before"], row["after"], row["change_type_label"],
            )).casefold()]
        groups = group_changes(rows)
        page = groups[offset:offset + limit]
        next_offset = offset + len(page)
        return {
            "job_id": job_id,
            "count": len(groups),
            "field_count": len(rows),
            "offset": offset,
            "limit": limit,
            "next_offset": next_offset if next_offset < len(groups) else None,
            "groups": page,
        }

    def shutdown(self) -> None:
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
