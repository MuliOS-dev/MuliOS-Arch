#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${1:-$ROOT/profile/packages}"
mkdir -p "$REPO_DIR"

command -v pacman >/dev/null || { printf 'ERROR: pacman is required.\n' >&2; exit 1; }
command -v repo-add >/dev/null || { printf 'ERROR: repo-add is required.\n' >&2; exit 1; }

python3 - "$REPO_DIR" <<'PY'
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
packages = sorted(
    package for package in repo.glob("*.pkg.tar.*")
    if not package.name.endswith(".sig")
)
if not packages:
    raise SystemExit(f"ERROR: no built packages found in {repo}")

latest = {}
for package in packages:
    result = subprocess.run(
        ["pacman", "-Qp", "--print-format", "%n\t%v", str(package)],
        check=True, capture_output=True, text=True,
    )
    name, version = result.stdout.strip().split("\t", 1)
    current = latest.get(name)
    if current is None:
        latest[name] = (version, package)
        continue
    comparison = subprocess.run(
        ["vercmp", version, current[0]], check=True, capture_output=True, text=True
    ).stdout.strip()
    if int(comparison) > 0:
        latest[name] = (version, package)

selected = [str(item[1]) for _, item in sorted(latest.items())]
for pattern in ("mulios.db*", "mulios.files*"):
    for stale in repo.glob(pattern):
        stale.unlink()

database = repo / "mulios.db.tar.zst"
print(f"Refreshing repository: {repo}")
print(f"Package archives found: {len(packages)}")
print(f"Unique package names: {len(selected)}")
for name, (version, package) in sorted(latest.items()):
    print(f"  {name} {version} <- {package.name}")

subprocess.run(["repo-add", "--wait-for-lock", str(database), *selected], check=True)
print("Local repository database regenerated successfully.")
PY
