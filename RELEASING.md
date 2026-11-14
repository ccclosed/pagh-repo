# Releasing

This is the operational runbook for **pagh-repo**, the package repository served
to the `pkg` installer in pagh-riscv. The branch model is in `BRANCHING.md`; the
wire format is in [`docs/package-format.md`](docs/package-format.md). Nothing
here releases automatically except the tag-driven `release` workflow in
`.github/workflows/release.yml`.

## The one hard rule: stable packages only

`index` and `pkg/` carry **stable releases only** — a `paghbox` build produced
from a **stable `vX.Y.Z` tag on `pagh-programs` `main`**. A package built from a
`pagh-programs` `dev` commit, from an `-rc.N` tag, or from any other
pre-release is **never** committed here: pre-releases only create GitHub
pre-releases in `pagh-programs`, and users installing from this repository must
never receive one. The only path into `index` is:

```
pagh-programs stable tag vX.Y.Z (main)
  -> cargo build --release + tools/build_repo.py  (stable .ppkg in repo/)
  -> pagh-repo tools/publish.py                    (digest/size gate)
  -> pagh-repo tools/verify.py                     (CI gate)
  -> pagh-repo PR to dev -> merge to main -> tag vX.Y.Z
```

## Version sources

| Repository | Version source |
|---|---|
| Pagh-OS, pagh-riscv, pagh-python, pagh-rust | `Cargo.toml` (`[package].version`; workspace members as documented below) |
| pagh-libc | `VERSION` |
| pagh-api | `libpagh/Cargo.toml` |
| pagh-programs | `programs/Cargo.toml` |
| pagh-repo | index manifest version |

**This repository:** the version source is the `index` manifest, not a Cargo
file. `index` starts with `PPKGINDEX 1`, and each following line is a
tab-separated package record `name version sha256 size kind commands url`; the
release version is the version field of the first record (today the single
`paghbox` package). The release workflow sets `VERSION_FILE: index` and parses
that field, and the tag base `X.Y.Z` must equal it. The `README.md` "Сейчас"
sentence quotes the same version/size/SHA-256 and is checked by
`tools/verify.py`, so the published figures cannot drift from the manifest
silently.

`dev` carries the **next publication** (the index/pkg state prepared from the
latest stable `pagh-programs` release). `main` keeps the last **published**
state. A stable tag `vX.Y.Z` must equal the index version on `main`.

## Pre-release (release candidate) — from `dev` only

Pre-release tags in this repository exist only to exercise the release workflow;
they are **never** a publication mechanism for packages.

1. Freeze `dev` if the RC is meant to validate the exact upcoming stable tag.
2. Pre-flight on the exact `dev` commit:
   - CI green (job `verify`: `python3 tools/verify.py`);
   - the `index`/`pkg` content already corresponds to a stable
     `pagh-programs` release (a pre-release package in the tree is a blocker,
     not a warning);
   - version source (`index`) equals `X.Y.Z`;
   - no open blocker.
3. Tag and push `vX.Y.Z-rc.N`:
   ```sh
   git checkout dev && git pull --ff-only
   git tag -a vX.Y.Z-rc.1 -m "pagh-repo X.Y.Z-rc.1"
   git push origin vX.Y.Z-rc.1
   ```
4. Watch the `release` workflow: it refuses the tag unless it is reachable from
   `dev` **and not** from `main`, checks that the tag base equals the `index`
   version, runs `tools/verify.py`, and publishes a GitHub **Pre-release** with
   the source archive and its `.sha256`.
   A rejected tag stays in the repository but produces **no** release entry:
   delete it (`git push origin :refs/tags/<tag>`) before retrying.
5. Test the pre-release archive (extract, `python3 tools/verify.py`, serve it
   with `serve.sh` and install from it in QEMU if needed). Bugs: fix on `dev`,
   tag `-rc.2` (never move the `-rc.1` tag).

## Stable release — from `main`

1. Merge `dev` into `main` (merge commit; no content changes at this step):
   ```sh
   git checkout main && git pull --ff-only
   git merge --no-ff dev
   git push origin main
   ```
2. Wait for CI on `main` to be green (`tools/verify.py`).
3. Tag and push `vX.Y.Z` on the merge commit; the workflow checks that the
   commit is reachable from `main` and that `index` says `X.Y.Z`.
4. Verify in **Releases**: the new entry is a full release with
   `<repo>-vX.Y.Z.tar.gz` (contains `index` and `pkg/*.ppkg`) and matching
   `.sha256`. GitHub marks the newest stable as **Latest**.
5. `dev` continues with the next publication once a newer stable `pagh-programs`
   release exists.

## Publishing a new package (the normal update)

This is the only supported way `index`/`pkg` change. It runs **after**
`pagh-programs` has a stable tag on `main`; move the packages from that tag:

```sh
# in pagh-programs, on the stable vX.Y.Z tag
cargo build --release --target riscv64gc-unknown-none-elf
python3 tools/build_repo.py
python3 tools/build_repo.py --check

# in pagh-repo, on dev
python3 tools/publish.py ../pagh-programs/repo
python3 tools/verify.py
git add -A && git commit -m "repo: publish paghbox X.Y.Z"
```

Open a PR against `dev` and let CI run `tools/verify.py`; `publish.py` refuses
any size/SHA-256 mismatch and `verify.py` re-parses every package (including the
historical ones that stay in `pkg/` without an index line). Merge to `dev`,
then follow the stable release flow above. If the stable `pagh-programs` release
is a PATCH hotfix, publish it the same way and cut a PATCH tag here.

## Hotfix — straight to `main`, no RC

Hotfixes are limited to **critical/high verified security findings** or a
release-blocking regression in a published package. Everything else rides `dev`.

1. Branch from `main`: `hotfix/<short-name>`.
2. PR to `main` (never to `dev`) with the corrected package/`index` (or a
   revert), plus `python3 tools/verify.py` in the description. Get it reviewed.
3. Merge to `main`, then tag the PATCH release `vX.Y.Z+1` directly (no RC) and
   verify the release entry.
4. Merge `main` back into `dev` with `--no-ff`:
   ```sh
   git checkout dev && git pull --ff-only
   git merge --no-ff main
   ```
   Resolve version conflicts in favour of the larger version (dev stays ahead).
5. CI on `dev` must be green after the merge-back.

## Cross-repository ABI change order

When a change touches the C/ABI boundary, release in dependency order and only
then update dependants:

1. `pagh-api` / `pagh-libc` (whichever changed; if both, `pagh-api` first when
   the SDK pins the libc header).
2. `pagh-rust` / `pagh-python` (they consume `pagh-api`/`pagh-libc`).
3. `pagh-programs` (apps built against the new SDK), `pagh-repo` (published
   packages), and finally Pagh-OS / pagh-riscv images that ship the new
   runtime/ABI.
4. Update the pinned sibling versions (`Cargo.toml` path/registry deps,
   `Cargo.lock`) in the same release train, not later.

Never tag a dependant before its dependency is tagged; the release workflow
only checks branch/version, not cross-repo compatibility.

## Backfill and "Latest"

GitHub marks **Latest** by release creation time, not by version number. When
backfilling already-released versions, create tags in ascending version order
(oldest first), so the newest version is created last and becomes Latest.

## Rollback / mistakes

- Wrong tag on the wrong commit: delete the release (`gh release delete <tag>
  --yes`) and the tag (`git push origin :refs/tags/<tag>`), fix, retag.
- Workflow rejected the tag: delete the tag; no release exists to clean up.
- A wrong `.ppkg` reached `main`: revert the publish commit (the previous
  `pkg/` files stay as history), run `python3 tools/verify.py`, and publish the
  corrected stable build. Prefer a PATCH publication over rewriting `main`.
- Bad stable release: prefer a PATCH hotfix over moving/deleting a published
  tag; if the release is minutes old and nothing depends on it, delete
  release + tag, then re-tag the fixed commit.
- Never move an existing tag; immutable tags are enforced by the tag ruleset.

## Release checklist (paste into the release PR / notes)

- [ ] `index` version equals the stable `pagh-programs` tag base
- [ ] Every package in `index` came from a **stable** `pagh-programs` release (no `-rc.N`, no `dev` build)
- [ ] `tools/publish.py` accepted the package (size/SHA-256)
- [ ] `tools/verify.py` green (CI and locally)
- [ ] README "Сейчас" figures match `index`
- [ ] CI green on the exact commit
- [ ] Freeze respected (no content merges after `-rc.1`)
- [ ] Source archive + `.sha256` extracted and verified once
- [ ] `main`/`dev` synchronized per the flow above
- [ ] Release entry has the right type (Pre-release vs Release)