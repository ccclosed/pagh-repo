#!/usr/bin/env python3
"""Verify this package repository: index, current packages, historical packages.

    python3 tools/verify.py
    python3 tools/verify.py --repo .

CI runs exactly this command. It is the read-only twin of `tools/publish.py`:
publish.py checks a *built* `repo/` directory before copying it here, while this
script checks what is actually committed (or about to be pushed) and is the only
gate the repository has until package signatures land.

Checks:

* `index` starts with `PPKGINDEX 1` and every line has the seven tab fields;
* every indexed package exists, its **whole-file** size and SHA-256 match the
  index (the installer's download gate), and its manifest (`name`, `version`,
  `arch`, `kind`, `commands`) matches the index line;
* the manifest's own `sha256` matches the ELF payload, and the payload is an
  ELF64 little-endian RISC-V executable whose entry point is inside the ABI's
  user window;
* every `pkg/*.ppkg` is a well-formed `.ppkg` — historical versions stay in
  `pkg/` without an index line on purpose, so they are validated by their own
  manifest and filename, not by the index;
* no foreign files under `pkg/`, no duplicate package names in the index.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAGIC = b"PPKG0001"
INDEX_MAGIC = "PPKGINDEX 1"
ARCH = "riscv64"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")
REQUIRED_MANIFEST = {
    "name",
    "version",
    "arch",
    "kind",
    "commands",
    "description",
    "sha256",
}
OPTIONAL_MANIFEST = {"entry"}


class VerifyError(Exception):
    """A repository inconsistency with a human-readable reason."""


def read(path: pathlib.Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise VerifyError(f"cannot read {path}: {error}") from error


def parse_manifest(raw: bytes, where: str) -> dict[str, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VerifyError(f"{where}: manifest is not UTF-8: {error}") from error
    values: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line:
            raise VerifyError(f"{where}: manifest line {number} is empty")
        if "=" not in line:
            raise VerifyError(f"{where}: manifest line {number} has no '='")
        key, value = line.split("=", 1)
        if key in values:
            raise VerifyError(f"{where}: duplicate manifest key {key!r}")
        values[key] = value
    missing = REQUIRED_MANIFEST - values.keys()
    if missing:
        raise VerifyError(f"{where}: manifest missing keys: {', '.join(sorted(missing))}")
    unknown = values.keys() - REQUIRED_MANIFEST - OPTIONAL_MANIFEST
    if unknown:
        raise VerifyError(f"{where}: manifest has unknown keys: {', '.join(sorted(unknown))}")
    return values


def parse_package(path: pathlib.Path) -> tuple[dict[str, str], bytes, bytes]:
    data = read(path)
    if len(data) < 16 or data[:8] != MAGIC:
        raise VerifyError(f"{path}: bad or missing PPKG0001 magic")
    manifest_len, payload_len = struct.unpack_from("<II", data, 8)
    if len(data) != 16 + manifest_len + payload_len:
        raise VerifyError(
            f"{path}: length {len(data)} != 16 + manifest {manifest_len} + payload {payload_len}"
        )
    manifest = parse_manifest(data[16 : 16 + manifest_len], str(path))
    payload = data[16 + manifest_len :]
    validate_elf(payload, str(path))
    if manifest["sha256"] != hashlib.sha256(payload).hexdigest():
        raise VerifyError(f"{path}: manifest sha256 does not match the payload")
    return manifest, payload, data


def validate_elf(payload: bytes, where: str) -> None:
    if len(payload) < 64 or payload[:4] != b"\x7fELF":
        raise VerifyError(f"{where}: payload is not an ELF")
    if payload[4] != 2:
        raise VerifyError(f"{where}: payload is not ELFCLASS64")
    if payload[5] != 1:
        raise VerifyError(f"{where}: payload is not little-endian")
    e_type, e_machine, _version = struct.unpack_from("<HHI", payload, 16)
    if e_type not in (2, 3):
        raise VerifyError(f"{where}: e_type={e_type}, expected ET_EXEC/ET_DYN")
    if e_machine != 243:
        raise VerifyError(f"{where}: e_machine={e_machine}, expected RISC-V (243)")
    entry = struct.unpack_from("<Q", payload, 24)[0]
    if entry < 0x10000:
        raise VerifyError(f"{where}: entry point {entry:#x} is below 0x10000")


def verify(repo: pathlib.Path) -> int:
    index_path = repo / "index"
    if not index_path.is_file():
        raise VerifyError(f"{index_path} does not exist")
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise VerifyError(f"cannot read {index_path}: {error}") from error
    if not lines or lines[0] != INDEX_MAGIC:
        raise VerifyError(f"{index_path}: first line must be {INDEX_MAGIC!r}")

    referenced: set[pathlib.Path] = set()
    seen: set[str] = set()
    packages = 0
    for number, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            raise VerifyError(f"{index_path}:{number}: expected 7 tab fields, got {len(fields)}")
        name, version, digest, size_text, kind, commands, url = fields
        where = f"{index_path}:{number}"
        if not NAME.fullmatch(name):
            raise VerifyError(f"{where}: invalid package name {name!r}")
        if name in seen:
            raise VerifyError(f"{where}: duplicate package {name!r}")
        seen.add(name)
        if not version:
            raise VerifyError(f"{where}: empty version")
        if not HEX64.fullmatch(digest):
            raise VerifyError(f"{where}: sha256 is not 64 lowercase hex digits")
        try:
            size = int(size_text)
        except ValueError as error:
            raise VerifyError(f"{where}: size {size_text!r} is not an integer") from error
        if size <= 0:
            raise VerifyError(f"{where}: size must be positive")
        if kind not in ("app", "applet-bundle"):
            raise VerifyError(f"{where}: kind {kind!r} is not app/applet-bundle")
        if not commands:
            raise VerifyError(f"{where}: commands is empty")
        if url.startswith("/") or ".." in url.split("/"):
            raise VerifyError(f"{where}: url {url!r} must be relative and stay in the repo")

        package_path = (repo / url).resolve()
        try:
            package_path.relative_to(repo.resolve())
        except ValueError as error:
            raise VerifyError(f"{where}: url {url!r} escapes the repository") from error
        if not package_path.is_file():
            raise VerifyError(f"{where}: {package_path} does not exist")
        referenced.add(package_path)

        manifest, _payload, data = parse_package(package_path)
        if manifest["name"] != name:
            raise VerifyError(f"{where}: manifest name {manifest['name']!r} != {name!r}")
        if manifest["version"] != version:
            raise VerifyError(f"{where}: manifest version {manifest['version']!r} != {version!r}")
        if manifest["arch"] != ARCH:
            raise VerifyError(f"{where}: manifest arch {manifest['arch']!r} != {ARCH!r}")
        if manifest["kind"] != kind:
            raise VerifyError(f"{where}: manifest kind {manifest['kind']!r} != {kind!r}")
        if manifest["commands"] != commands:
            raise VerifyError(f"{where}: manifest commands differ from the index")
        if len(data) != size:
            raise VerifyError(
                f"{where}: index size {size} != package length {len(data)} "
                "(the index describes the whole .ppkg)"
            )
        if hashlib.sha256(data).hexdigest() != digest:
            raise VerifyError(f"{where}: package sha256 != index {digest}")
        packages += 1

    # Historical packages: well-formed and internally consistent, not indexed.
    pkg_dir = repo / "pkg"
    if not pkg_dir.is_dir():
        raise VerifyError(f"{pkg_dir} does not exist")
    historical = 0
    for path in sorted(pkg_dir.iterdir()):
        if path.suffix != ".ppkg":
            raise VerifyError(f"{pkg_dir}: unexpected file {path.name!r}")
        if path.resolve() in referenced:
            continue
        manifest, _payload, _data = parse_package(path)
        expected = f"{manifest['name']}-{manifest['version']}.ppkg"
        if path.name != expected:
            raise VerifyError(f"{path}: manifest says {expected!r}")
        if manifest["arch"] != ARCH:
            raise VerifyError(f"{path}: manifest arch {manifest['arch']!r} != {ARCH!r}")
        historical += 1

    print(
        f"OK: {index_path} lists {packages} package(s); "
        f"{historical} historical package(s) valid; all digests and manifests agree"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=pathlib.Path,
        default=ROOT,
        help=f"repository directory to verify (default: {ROOT})",
    )
    args = parser.parse_args()
    try:
        return verify(args.repo)
    except VerifyError as error:
        print(f"verify: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())