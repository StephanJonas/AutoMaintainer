from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any

from .integrations import run


def git(cwd: str, *args: str) -> str:
    proc = run(["git", *args], cwd=cwd, timeout=60)
    if proc.returncode:
        raise RuntimeError(proc.stdout[-3000:])
    return proc.stdout.strip()


def changed_files(worktree: str, base_sha: str) -> list[str]:
    return git(worktree, "diff", "--name-only", f"{base_sha}...HEAD").splitlines()


def check_diff(project: dict[str, Any], worktree: str, base_sha: str, cfg: dict[str, Any]) -> tuple[bool, str, list[str]]:
    files = changed_files(worktree, base_sha)
    if not files:
        return False, "Der Agent hat keine Änderungen erzeugt", files
    for name in files:
        if any(fnmatch.fnmatch(name, pattern) for pattern in project["protected_paths"]):
            return False, f"Geschützte Datei verändert: {name}", files
        if project.get("allowed_paths") and not any(fnmatch.fnmatch(name, pattern) for pattern in project["allowed_paths"]):
            return False, f"Datei außerhalb der erlaubten Pfade: {name}", files
    if len(files) > cfg.get("max_changed_files", 12):
        return False, f"Diff umfasst {len(files)} Dateien; Limit überschritten", files
    stat = git(worktree, "diff", "--numstat", f"{base_sha}...HEAD")
    lines = sum(int(p) for row in stat.splitlines() for p in row.split("\t")[:2] if p.isdigit())
    if lines > cfg.get("max_diff_lines", 700):
        return False, f"Diff umfasst {lines} geänderte Zeilen; Limit überschritten", files
    return True, f"Diff-Regeln erfüllt ({len(files)} Dateien, {lines} Zeilen)", files


def run_commands(commands: list[list[str]], cwd: str) -> list[dict[str, Any]]:
    results = []
    for command in commands:
        proc = run(command, cwd=cwd, timeout=1800)
        results.append({"command": command, "returncode": proc.returncode, "output": proc.stdout[-12000:]})
        if proc.returncode:
            break
    return results
