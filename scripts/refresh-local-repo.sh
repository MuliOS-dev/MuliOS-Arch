#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="${1:-$ROOT/profile/packages}"
mkdir -p "$REPO_DIR"

for command in bsdtar repo-add vercmp; do
    command -v "$command" >/dev/null || { printf 'ERROR: %s is required.\n' "$command" >&2; exit 1; }
done

python3 - "$REPO_DIR" <<'PY'
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
packages = sorted(
    path for path in repo.glob("*.pkg.tar.*")
    if not path.name.endswith(".sig")
)
if not packages:
    raise SystemExit(f"ERROR: no package archives found in {repo}")

def metadata(package):
    result = subprocess.run(
        ["bsdtar", "-xOf", str(package), ".PKGINFO"],
        check=True, capture_output=True, text=True,
    )
    values = {}
    for line in result.stdout.splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            if key in ("pkgname", "pkgver"):
                values[key] = value
    if not values.get("pkgname") or not values.get("pkgver"):
        raise SystemExit(f"ERROR: missing pkgname/pkgver in {package.name}")
    return values["pkgname"], values["pkgver"]

latest = {}
for package in packages:
    name, version = metadata(package)
    current = latest.get(name)
    if current is None:
        latest[name] = (version, package)
        continue
    comparison = subprocess.run(
        ["vercmp", version, current[0]],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if int(comparison) > 0:
        latest[name] = (version, package)

selected = [str(item[1]) for _, item in sorted(latest.items())]
print(f"Local package archives: {len(packages)}")
print(f"Unique packages: {len(selected)}")
for name, (version, package) in sorted(latest.items()):
    print(f"  {name} {version} ({package.name})")

for pattern in ("mulios.db*", "mulios.files*"):
    for stale in repo.glob(pattern):
        stale.unlink()

database = repo / "mulios.db.tar.zst"
subprocess.run(["repo-add", "--wait-for-lock", str(database), *selected], check=True)
print("Local package database refreshed.")
PY
