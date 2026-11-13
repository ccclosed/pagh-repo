# Branching and releases

## Branches

| Branch | Role | Rules |
|---|---|---|
| `main` | **Stable.** The published package index and packages users consume. | Only release merges from `dev` (or a hotfix PR) land here. CI must be green. |
| `dev` | **Experimental integration.** Next publication is prepared here and may be broken between commits. | Feature/fix PRs target `dev`. CI must be green before merge. |
| `feat/*`, `fix/*`, `security/*` | Short-lived work branches. | Branch from `dev`, PR back to `dev`, delete after merge. |

`main` and `dev` are both protected in spirit: no direct pushes of code, no
force-pushes, CI green before merge. Tagging and release publication are
maintainer actions.

## Release flow

1. **Feature / fix PR** → `dev`. CI runs the same gates as for `main`.
2. **Pre-release** (optional but recommended): tag a validated `dev` commit
   `vX.Y.Z-rc.N` (or `-pre.N` for an experimental snapshot) and push the tag.
   `.github/workflows/release.yml` publishes it as a **GitHub pre-release**
   (GitHub marks it "Pre-release"; package tooling must ignore it unless the
   user opts in).
3. **Stabilisation**: once `dev` is release-ready, merge `dev` → `main` (merge
   commit or fast-forward, no code changes beyond release metadata).
4. **Stable release**: tag the merge commit `vX.Y.Z` on `main`; the release
   workflow publishes a full GitHub release with generated notes.
5. **Hotfix**: branch from `main`, PR to `main`, tag a PATCH version; afterwards
   merge `main` back into `dev` so the next release does not regress the fix.

## Published packages

Published packages correspond to **stable releases only**. `index` and `pkg/`
must carry a `paghbox` build taken from a `main`-tagged release of
[`pagh-programs`](https://github.com/ccclosed/pagh-programs); a version merged to
`dev` (or tagged `-rc.N`/`-pre.N`) is a pre-release and is **not** published
here until it is stabilised on `main`. Pre-release tags only create GitHub
pre-releases — they never update `index`.

## Tag conventions

| Tag | Cut from | GitHub release type |
|---|---|---|
| `vX.Y.Z` (or bare `X.Y.Z` where historically used) | `main` | Release |
| `vX.Y.Z-rc.N` | `dev` | Pre-release |
| `vX.Y.Z-pre.N` | `dev` | Pre-release |

The version source of truth is the `index` manifest — the package version it
publishes, together with the `pkg/*.ppkg` files it points at — and the version
figures in `README.md` mirror it; a tag must match it. The release workflow
checks ancestry, not the version string — the version bump and the tag are made
in the same release step by a maintainer.

## Why two branches

`main` stays reproducible for users and downstream repositories (whose packages
or kernels point at releases). `dev` lets integration work — multi-repo changes,
experimental features, unfinished migrations — land and be tested continuously
without making `main` unstable.