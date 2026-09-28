from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.parse
import urllib.request
from typing import Any


class Jira:
    def __init__(self):
        self.base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        self.email = os.environ.get("JIRA_EMAIL", "")
        self.token = os.environ.get("JIRA_API_TOKEN", "")
        if not all((self.base, self.email, self.token)):
            raise RuntimeError("JIRA_BASE_URL, JIRA_EMAIL und JIRA_API_TOKEN müssen gesetzt sein")

    def search(self, jql: str) -> list[dict[str, Any]]:
        auth = base64.b64encode(f"{self.email}:{self.token}".encode()).decode()
        payload = json.dumps({"jql": jql, "maxResults": 100, "fields": ["summary", "description", "issuetype", "status", "labels", "project"]}).encode()
        req = urllib.request.Request(self.base + "/rest/api/3/search/jql", data=payload, headers={"Authorization": f"Basic {auth}", "Accept": "application/json", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.load(response)
        return data.get("issues", [])


def run(argv: list[str], cwd: str | None = None, timeout: int = 900, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)


def gh(repo: str, *args: str, check: bool = True, timeout: int = 60, cwd: str | None = None) -> str:
    proc = run(["gh", "--repo", repo, *args], cwd=cwd, timeout=timeout)
    if check and proc.returncode:
        raise RuntimeError(f"gh {args[0]} fehlgeschlagen: {proc.stdout[-3000:]}")
    return proc.stdout
