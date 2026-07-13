#!/bin/zsh
set -euo pipefail

cd "${0:A:h}/.."

if ! command -v uv >/dev/null 2>&1; then
  print -u2 "PalEdit 需要 uv。请先执行：brew install uv"
  exit 1
fi

tile_root="src/paledit/static/map/tiles"
tile_count=$(find "$tile_root" -type f -name '*.png' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$tile_count" != "5461" ]] || grep -q '^version https://git-lfs.github.com/spec/v1$' "$tile_root/6/32/32.png" 2>/dev/null; then
  print -u2 "PalEdit 高分辨率地图瓦片不完整。请先安装 Git LFS 并执行：git lfs pull"
  exit 1
fi

uv sync --extra dev
open "http://127.0.0.1:18765"
exec uv run paledit serve
