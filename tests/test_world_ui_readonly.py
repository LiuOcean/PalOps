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
