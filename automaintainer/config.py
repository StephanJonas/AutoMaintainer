from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def expand(value: str) -> str:
    return str(Path(value).expanduser())


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config nicht gefunden: {path}; kopiere config.example.toml nach config.toml")
    cfg = tomllib.loads(path.read_text())
    cfg.setdefault("state_dir", "~/.local/state/automaintainer")
    cfg.setdefault("worktree_dir", "~/Library/Caches/automaintainer/worktrees")
    cfg.setdefault("database", "~/.local/state/automaintainer/state.sqlite3")
    cfg["state_dir"] = expand(cfg["state_dir"])
    cfg["worktree_dir"] = expand(cfg["worktree_dir"])
    cfg["database"] = expand(cfg["database"])
    cfg.setdefault("projects", [])
    if not cfg["projects"]:
        raise ValueError("Mindestens ein [[projects]]-Eintrag ist erforderlich")
    for project in cfg["projects"]:
        project["path"] = expand(project["path"])
        for required in ("key", "github_repo", "base_branch", "protected_paths", "test_commands"):
            if required not in project:
                raise ValueError(f"Projekt {project.get('key', '?')}: Konfiguration {required} fehlt")
    return cfg
