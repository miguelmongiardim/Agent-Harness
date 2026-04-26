from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-bytes", type=int, required=True)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)

    oversized = [
        path
        for path in (Path(raw) for raw in args.paths)
        if path.is_file() and path.stat().st_size > args.max_bytes
    ]
    for path in oversized:
        print(f"{path}: file exceeds {args.max_bytes} bytes", file=sys.stderr)
    return 1 if oversized else 0


if __name__ == "__main__":
    raise SystemExit(main())
