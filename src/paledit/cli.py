import argparse
import json
from pathlib import Path

from .parser import load_character_data
from .save import discover_worlds, sha256


def main() -> None:
    parser = argparse.ArgumentParser(prog="palops")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="只读检查世界存档")
    inspect_parser.add_argument("world", type=Path)
    serve_parser = subparsers.add_parser("serve", help="启动本地管理控制台")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", default=18765, type=int)
    discover_parser = subparsers.add_parser("discover", help="发现服务器世界")
    discover_parser.add_argument("root", nargs="?", default="Save", type=Path)
    args = parser.parse_args()

    if args.command == "discover":
        print(json.dumps([world.dump() for world in discover_worlds(args.root)], ensure_ascii=False, indent=2))
    elif args.command == "inspect":
        level = args.world.expanduser().resolve() / "Level.sav"
        result = load_character_data(level)
        print(json.dumps({
            "world": args.world.name,
            "sha256": sha256(level),
            "character_count": result["character_count"],
            "world_property_count": result["world_property_count"],
            "write_enabled": True,
        }, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        import uvicorn
        uvicorn.run("paledit.api:app", host=args.host, port=args.port, reload=False)
