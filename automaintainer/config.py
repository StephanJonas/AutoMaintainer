from __future__ import annotations

import tomllib
import os
import re
import stat
from pathlib import Path
from typing import Any


def expand(value: str) -> str:
    return str(Path(value).expanduser())


def load_env_file(path: Path) -> None:
    """Load simple KEY=value entries without evaluating shell syntax."""
    if not path.is_file():
        return
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError(f"{path} muss nur für dich lesbar sein; setze die Rechte mit chmod 600 {path}")
    for line_number, source_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = source_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"Ungültiger Eintrag in {path}, Zeile {line_number}; erwartet wird KEY=value")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Config nicht gefunden: {path}; kopiere config.example.toml nach config.toml")
    cfg = tomllib.loads(path.read_text())
    cfg.setdefault("state_dir", "~/.local/state/automaintainer")
    cfg.setdefault("worktree_dir", "~/Library/Caches/automaintainer/worktrees")
    cfg.setdefault("database", "~/.local/state/automaintainer/state.sqlite3")
    cfg.setdefault("ollama_url", "http://127.0.0.1:11434")
    cfg.setdefault("ollama_model", "qwen3.6:35b-a3b-coding")
    cfg["state_dir"] = expand(cfg["state_dir"])
    cfg["worktree_dir"] = expand(cfg["worktree_dir"])
    cfg["database"] = expand(cfg["database"])
    cfg.setdefault("jira", {})
    cfg.setdefault("security_profiles", {})
    cfg.setdefault("projects", [])
    if not cfg["projects"]:
        raise ValueError("Mindestens ein [[projects]]-Eintrag ist erforderlich")
    seen_jira_keys: set[str] = set()
    for project in cfg["projects"]:
        if "jira_project_key" not in project:
            raise ValueError(f"Projekt {project.get('key', '?')}: jira_project_key fehlt")
        jira_key = project["jira_project_key"]
        if jira_key in seen_jira_keys:
            raise ValueError(f"Jira-Projekt {jira_key} ist mehrfach konfiguriert")
        seen_jira_keys.add(jira_key)
        project.setdefault("key", jira_key.lower())
        project.setdefault("issue_prefix", jira_key + "-")
        repos = project.get("repos")
        if not repos:
            raise ValueError(f"Jira-Projekt {jira_key}: mindestens ein [[projects.repos]]-Eintrag ist erforderlich")
        seen_repo_keys: set[str] = set()
        for index, repo in enumerate(repos, start=1):
            repo.setdefault("key", repo.get("github_repo", f"repo-{index}"))
            if repo["key"] in seen_repo_keys:
                raise ValueError(f"Jira-Projekt {jira_key}: Repo-Schlüssel {repo['key']} ist doppelt")
            seen_repo_keys.add(repo["key"])
            for required in ("path", "github_repo", "base_branch", "protected_paths", "test_commands"):
                if required not in repo:
                    raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: Konfiguration {required} fehlt")
            repo["path"] = expand(repo["path"])
            dependency_paths = repo.get("dependency_paths", [])
            if not isinstance(dependency_paths, list) or any(not isinstance(pattern, str) or not pattern for pattern in dependency_paths):
                raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: dependency_paths muss eine Liste nichtleerer Pfadmuster sein")
            if repo.get("security_auto_remediate") and not repo.get("dependency_paths"):
                raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: security_auto_remediate benötigt eine dependency_paths-Allowlist")
            if repo.get("security_auto_remediate") and not repo.get("security_commands"):
                raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: security_auto_remediate benötigt mindestens einen ausführbaren security_command")
            seen_target_keys: set[str] = set()
            for target in repo.get("security_targets", []):
                target_key = target.get("key", "")
                if not target_key or target_key in seen_target_keys:
                    raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: security_targets brauchen eindeutige key-Werte")
                seen_target_keys.add(target_key)
                target_path = Path(target.get("path", ""))
                if not target.get("path") or target_path.is_absolute() or ".." in target_path.parts:
                    raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}, Ziel {target_key}: path muss relativ zum Repo und ohne '..' sein")
                profile = target.get("profile", "")
                profile_config = cfg["security_profiles"].get(profile)
                if not profile_config or not str(profile_config.get("prompt", "")).strip():
                    raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}, Ziel {target_key}: unbekanntes oder leeres Security-Profil {profile!r}")
        if len(repos) > 1:
            for repo in repos:
                if not repo.get("jira_components"):
                    raise ValueError(f"Jira-Projekt {jira_key}, Repo {repo['key']}: jira_components ist bei mehreren Repos erforderlich")
    return cfg
