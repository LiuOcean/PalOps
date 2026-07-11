#!/bin/zsh
set -euo pipefail

cd "${0:A:h}/.."

if ! command -v uv >/dev/null 2>&1; then
  print -u2 "PalEdit 需要 uv。请先执行：brew install uv"
  exit 1
fi

uv sync --extra dev
open "http://127.0.0.1:18765"
exec uv run paledit serve
