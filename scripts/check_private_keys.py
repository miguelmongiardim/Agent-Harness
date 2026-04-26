from __future__ import annotations

import sys
from pathlib import Path

PRIVATE_KEY_MARKERS = (
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
)


def main(argv: list[str] | None = None) -> int:
    paths = [Path(raw) for raw in (argv if argv is not None else sys.argv[1:])]
    findings: list[Path] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in PRIVATE_KEY_MARKERS):
            findings.append(path)

    for path in findings:
        print(f"{path}: private key marker detected", file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
