# Branching and releases

## Branches

| Branch | Role | Rules |
|---|---|---|
| `main` | **Stable.** The published package index and packages users consume. | Only release merges from `dev` (or a hotfix PR) land here. CI must be green. |
| `dev` | **Experimental integration.** The next publication is prepared here and may be broken between commits. | Feature/fix PRs target `dev`. CI must be green before merge. |
| `feat/*`, `fix/*`, `security/*` | Short-lived work branches. | Branch from `dev`, PR back to `dev`, delete after merge. |
| `hotfix/*` | Emergency fix for a published package. | Branch from `main`, PR to `main`; only critical/high verified security or a release-blocking regression. |

`main` and `dev` are both protected in spirit: no direct pushes of code, no
force-pushes, CI green before merge. Tagging and release publication are
maintainer actions.

## Release flow

1. **Feature / fix PR** → `dev`. CI runs the same gates as for `main`.
2. **Pre-release**: freeze `dev` and tag a validated `dev` commit
   `vX.Y.Z-rc.N` (release candidates only; there is no `-pre.N` channel) and
   push the tag. After `-rc.1` only stabilisation fixes land in `dev`.
   `.github/workflows/release.yml` publishes it as a **GitHub pre-release**
   (GitHub marks it "Pre-release"; package tooling must ignore it unless the
   user opts in). A pre-release tag only snapshots the repository: it never
   changes which packages are published.
3. **Stabilisation**: once `dev` is release-ready, merge `dev` → `main` (merge
   commit or fast-forward, no content changes beyond release metadata).
4. **Stable release**: tag the merge commit `vX.Y.Z` on `main`; the release
   workflow publishes a full GitHub release with generated notes and the source
   archive (`<repo>-vX.Y.Z.tar.gz` containing `index` and `pkg/*.ppkg`, with
   `.sha256`).
5. **Hotfix**: branch from `main`, PR to `main` with full CI plus a targeted
   regression check, tag a PATCH version **straight to stable** (no RC), then
   merge `main` back into `dev` with `--no-ff`; `dev` keeps the higher version.

## Published packages

Published packages correspond to **stable releases only**. `index` and `pkg/`
must carry a `paghbox` build taken from a `main`-tagged release of
[`pagh-programs`](https://github.com/ccclosed/pagh-programs); a version merged to
`pagh-programs` `dev` (or tagged `-rc.N`) is a pre-release and is **not**
published here until it is stabilised on `pagh-programs` `main`. Pre-release
tags only create GitHub pre-releases — they never update `index`, in either
repository.

## Tag conventions

| Tag | Cut from | GitHub release type |
|---|---|---|
| `vX.Y.Z` | `main` | Release |
| `vX.Y.Z-rc.N` | `dev` (must not already be on `main`) | Pre-release |

New tags always carry the `v` prefix (`vX.Y.Z`, `vX.Y.Z-rc.N`); old bare-numeric
tags stay as history. The version source of truth is the `index` manifest (the
version field of the first package record, today the single `paghbox` package)
together with the `pkg/*.ppkg` files it points at; the `README.md` figures
mirror it and `tools/verify.py` enforces the match. `dev` carries the next
publication, `main` the last published one. The release workflow checks both the
tag's branch (stable: main; RC: dev-only) and that the tag base equals the
version source. The operational checklist is in `RELEASING.md`.

## Why two branches

`main` stays reproducible for users and downstream repositories (whose packages
or kernels point at releases). `dev` lets integration work — multi-repo
changes, experimental features, unfinished migrations — land and be tested
continuously without making `main` unstable.