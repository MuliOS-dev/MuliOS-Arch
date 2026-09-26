#!/usr/bin/env python3

from pathlib import Path
import subprocess
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    task_manager = (
        repo_root
        / "profile"
        / "airootfs"
        / "opt"
        / "taskmanager"
        / "main.py"
    )

    if not task_manager.is_file():
        print(f"ERROR: Task Manager source not found: {task_manager}", file=sys.stderr)
        return 1

    return subprocess.call([sys.executable, str(task_manager)])


if __name__ == "__main__":
    raise SystemExit(main())
