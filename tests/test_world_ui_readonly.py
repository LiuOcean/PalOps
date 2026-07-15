from pathlib import Path


STATIC_ROOT = Path(__file__).parents[1] / "src" / "paledit" / "static"


def test_world_data_ui_exposes_read_only_controls() -> None:
    html = (STATIC_ROOT / "index.html").read_text()
    script = (STATIC_ROOT / "app.js").read_text()

    assert "世界数据 <span class=\"workspace-mode\"" in html
    assert html.count("readonly") >= 6
    assert 'class="pal-count"' in html
    assert "save-user" not in html
    assert "backup-restore-dialog" not in html
    assert "backup-delete-dialog" not in html
    assert "method:'PATCH'" not in script
    assert "/api/backups/restore" not in script
    assert "method:'DELETE'" not in script
    assert "编辑槽位" not in script


def test_backup_ui_exposes_two_version_read_only_comparison() -> None:
    html = (STATIC_ROOT / "index.html").read_text()
    script = (STATIC_ROOT / "app.js").read_text()

    assert 'id="backup-compare-tray"' in html
    assert 'data-page="backup-diff"' in html
    assert 'id="diff-important-only"' in html
    assert 'id="diff-retry"' in html
    assert 'id="diff-browser" class="panel diff-browser" aria-busy="false"' in html
    assert 'id="diff-timeline-start"' in html
    assert 'id="diff-inspector" class="diff-inspector"' in html
    assert "版本对比 · 变化轨迹" in html
    assert "world/backups/compare" in script
    assert "base_backup_id" in script
    assert "/api/backups/diffs" in script
    assert "backupDiffRequest?.abort()" in script
    assert "function resetBackupDiffFilters()" in script
    assert "function renderBackupDiffInspector(group)" in script
    assert "function selectBackupDiffGroup(groupId," in script
    assert "pals:'ph-paw-print'" in script
    assert "error.name === 'AbortError'" in script
    assert "结果不会修改服务器或备份文件" in html
