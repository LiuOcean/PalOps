import json
import subprocess
from pathlib import Path

from paledit import box_job
from paledit.settings import AppSettings


WORLD_ID = "A" * 32


def test_target_paths_keep_box_job_backup_outside_saved(monkeypatch) -> None:
    monkeypatch.setenv("PALWORLD_WORLD_ID", WORLD_ID)
    monkeypatch.setattr(
        box_job,
        "load_settings",
        lambda: AppSettings(
            ssh_host="palworld-server",
            remote_save_root="/srv/palworld/Pal/Saved",
        ),
    )

    host, world_id, world, backup_root = box_job._target_paths()

    assert host == "palworld-server"
    assert world_id == WORLD_ID
    assert world == f"/srv/palworld/Pal/Saved/SaveGames/0/{WORLD_ID}"
    assert backup_root == "/srv/palworld/palops-backups/box-job"
    assert not backup_root.startswith("/srv/palworld/Pal/Saved/")


def test_remote_pull_excludes_every_backup_tree(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def completed(arguments, **_kwargs):
        calls.append(arguments)

    monkeypatch.setattr(box_job.subprocess, "run", completed)

    box_job._rsync_from_remote(tmp_path, "palworld-server", "/srv/palworld/world")

    arguments = calls[0]
    excluded = [arguments[index + 1] for index, value in enumerate(arguments) if value == "--exclude"]
    assert excluded == ["backup/", "PalEdit-Backup/", "PalEdit-Remote-Backup/"]


def test_level_backup_copies_only_the_mutated_file(monkeypatch) -> None:
    calls: list[tuple[list[str], int]] = []

    def ssh(arguments: list[str], timeout: int = 30):
        calls.append((arguments, timeout))

    monkeypatch.setattr(box_job, "_ssh", ssh)

    backup = box_job._create_remote_level_backup(
        f"/srv/palworld/Pal/Saved/SaveGames/0/{WORLD_ID}",
        "/srv/palworld/palops-backups/box-job",
        WORLD_ID,
    )

    assert backup.startswith("/srv/palworld/palops-backups/box-job/")
    assert backup.endswith(f"/{WORLD_ID}")
    assert calls[0][0] == ["/bin/mkdir", "-p", backup]
    assert calls[1][0] == [
        "/bin/cp",
        "-p",
        f"/srv/palworld/Pal/Saved/SaveGames/0/{WORLD_ID}/Level.sav",
        f"{backup}/Level.sav",
    ]
    assert calls[2][0][:2] == ["python3", "-c"]
    assert "backup hash mismatch" in calls[2][0][2]
    assert calls[2][0][-2:] == [backup, f"/srv/palworld/Pal/Saved/SaveGames/0/{WORLD_ID}/Level.sav"]
    assert all(WORLD_ID not in argument or argument.endswith("Level.sav") or argument == backup for call, _ in calls for argument in call)


def test_level_backup_retention_is_scoped_and_reported(monkeypatch) -> None:
    calls: list[list[str]] = []

    def ssh(arguments: list[str], timeout: int = 30):
        calls.append(arguments)
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout=json.dumps({
                "policy_days": 7,
                "minimum_kept": 3,
                "count_before": 5,
                "deleted": ["old"],
                "count_after": 4,
            }),
            stderr="",
        )

    monkeypatch.setattr(box_job, "_ssh", ssh)

    result = box_job._prune_remote_level_backups("/srv/palworld/palops-backups/box-job")

    assert result["deleted"] == ["old"]
    assert calls[0][-3:] == ["/srv/palworld/palops-backups/box-job", "7", "3"]


def test_level_backup_retention_rejects_unrelated_root() -> None:
    try:
        box_job._prune_remote_level_backups("/srv/palworld/Pal/Saved")
    except ValueError as error:
        assert "拒绝清理" in str(error)
    else:
        raise AssertionError("unrelated root was accepted")
