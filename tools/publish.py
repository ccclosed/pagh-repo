#!/usr/bin/env python3
"""Validate a built repo/ directory and copy it into this repository.

Usage: python3 tools/publish.py ../pagh-programs/repo

The source directory must contain `index` and `pkg/*.ppkg`. Every index line is
checked against its package's size and SHA-256 before anything is copied; a
single mismatch aborts the publish. This is the only gate the repository has
until package signatures land.
"""
import hashlib
import pathlib
import shutil
import sys

MAGIC = b"PPKG0001"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: publish.py <built-repo-dir>", file=sys.stderr)
        return 2
    src = pathlib.Path(sys.argv[1])
    index = src / "index"
    if not index.is_file():
        print(f"publish: no index at {index}", file=sys.stderr)
        return 2
    lines = index.read_text().splitlines()
    if not lines or lines[0] != "PPKGINDEX 1":
        print("publish: bad index header", file=sys.stderr)
        return 2
    dst_pkg = pathlib.Path("pkg")
    dst_pkg.mkdir(exist_ok=True)
    for line in lines[1:]:
        if not line.strip():
            continue
        name, version, digest, size, kind, commands, url = line.split("\t")
        package = src / url
        if not package.is_file():
            print(f"publish: missing {package}", file=sys.stderr)
            return 1
        data = package.read_bytes()
        if len(data) != int(size):
            print(f"publish: {name}: size {len(data)} != index {size}", file=sys.stderr)
            return 1
        if hashlib.sha256(data).hexdigest() != digest:
            print(f"publish: {name}: sha256 mismatch", file=sys.stderr)
            return 1
        if not data.startswith(MAGIC):
            print(f"publish: {name}: not a .ppkg", file=sys.stderr)
            return 1
        shutil.copy2(package, dst_pkg / pathlib.Path(url).name)
        print(f"published {name}-{version} ({size} bytes)")
    shutil.copy2(index, "index")
    print(f"index: {len([l for l in lines[1:] if l.strip()])} package(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
