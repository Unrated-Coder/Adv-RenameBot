#!/usr/bin/env python3
"""Read-only host preflight for a real Telegram large-file benchmark.

This does not transfer data or create large files. Run it on the same VPS and
filesystem that will host the bot before executing the manual Telegram matrix.
"""
import json
import os
import platform
import shutil
import subprocess
import sys


def version(command):
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        return subprocess.check_output([executable, "-version"], text=True, stderr=subprocess.STDOUT).splitlines()[0]
    except Exception as exc:
        return f"{executable}: {exc}"


def main():
    target = os.path.abspath(os.environ.get("WORKSPACE_ROOT", "workspaces"))
    probe = target if os.path.exists(target) else os.path.dirname(target)
    usage = shutil.disk_usage(probe)
    report = {
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_cores": os.cpu_count(),
        "workspace_probe": probe,
        "disk_total_bytes": usage.total,
        "disk_free_bytes": usage.free,
        "ffmpeg": version("ffmpeg"),
        "ffprobe": version("ffprobe"),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
