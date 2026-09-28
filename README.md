# AutoMaintainer

Lokaler Wartungsdienst für Jira-Bugs und GitHub-Pull-Requests. Qwen Code bearbeitet ein Ticket ausschließlich in einem kurzlebigen Git-Worktree. Der Orchestrator erzwingt anschließend Dateiregeln, Tests und Scanner, bevor er einen Pull Request erstellt oder aktualisiert. Zugangsdaten werden aus der Umgebung gelesen.

## Sicherheitsmodell

- `protected_paths` sind nach dem Agentenlauf unveränderlich. Änderungen dort verwerfen den gesamten Lauf.
- Der Agent darf nur in seinem Wegwerf-Worktree schreiben. Er kann weder direkt auf den Zielbranch pushen noch mergen.
- Ein sauberer Patch muss außerhalb geschützter Pfade liegen, das konfigurierte Diff-Limit einhalten und alle Tests/Scanner bestehen.
- Nur der Orchestrator veröffentlicht einen PR und aktiviert optional GitHub Auto-Merge. Branchschutz und erforderliche CI-Checks müssen im Repository konfiguriert sein.
- Ein fehlgeschlagener oder mehrdeutiger Lauf wird als Eskalation protokolliert; er wird nicht gemergt.
- Das Modell prüft nicht seine eigene Sicherheit. Git-Diff-Regeln und Prüfkommandos entscheiden.

Auto-Merge kann nur sicher sein, wenn GitHub Branch Protection, erforderliche Statuschecks und mindestens ein geschützter Zielbranch eingerichtet sind. Der Bot bekommt nur die minimal nötigen Jira- und GitHub-Rechte. Release-Branches gehören nicht als `base_branch` in die Konfiguration.

## Voraussetzungen

- macOS, Python 3.11+, Git, Ollama, Qwen Code CLI (`qwen`) und GitHub CLI (`gh`).
- Qwen Code auf einen lokalen Ollama-kompatiblen Provider konfigurieren. Der Agent nutzt `qwen --prompt` im Repo-Worktree; die Provider-Konfiguration erfolgt in Qwen Code, nicht in diesem Repo.
- `gh auth login` mit Repo-Rechten für Branch/PR-Erstellung und Auto-Merge.
- Jira Cloud API-Token. Für Jira Data Center muss der Jira-Adapter angepasst werden.

## Einrichtung

```sh
cd ~/Development/AutoMaintainer
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp config.example.toml config.toml
```

`config.toml` auf Projekte, geschützte Pfade, Test- und Scan-Kommandos anpassen. Datei und lokale State-Daten sind gitignored.

Environment für Jira setzen (z.B. in einer nur für den Benutzer lesbaren Datei, die ein Wrapper-Skript lädt):

```sh
export JIRA_BASE_URL='https://example.atlassian.net'
export JIRA_EMAIL='maintainer@example.com'
export JIRA_API_TOKEN='...'
```

Zunächst nur auswerten, ohne externe Änderungen:

```sh
automaintainer run --dry-run
```

`--dry-run` fragt Jira ab und zeigt die geplanten Tickets/Scans; es startet keinen Agenten und erstellt keine PRs. Danach kann ein einzelnes Ticket gezielt ausgeführt werden:

```sh
automaintainer ticket PROJ-123
```

Vollständiger täglicher Durchlauf:

```sh
automaintainer run
```

## Zeitplan (launchd)

`launchd/com.local.automaintainer.plist.example` ist ein Beispiel für tägliche Ausführung. Der Dienst prüft anhand des lokalen Datums, ob der wöchentliche Scan fällig ist. Passe Benutzerpfad und Umgebungsvariablen-Wrapper an und installiere es als `~/Library/LaunchAgents/com.local.automaintainer.plist`. Jobs laufen, wenn der Mac eingeschaltet ist; verpasste Läufe werden beim nächsten Start nachgeholt.

## Ablauf und Eskalationen

Logs und Status liegen unter `~/.local/state/automaintainer/`. Jeder Lauf speichert Ticket/PR, Branch, Basis-Commit, Diff-Prüfung, Test- und Scan-Ergebnisse sowie Eskalationsgrund. Der erste Stand erzeugt PRs und aktiviert Auto-Merge nach bestandenem CI, wenn `auto_merge = true`. Nicht erfolgreiche Arbeiten erhalten keinen PR; Eskalationsmeldungen erscheinen im lokalen Log und in `automaintainer escalations`.

Ein Ticket mit bereits erstelltem PR wird nicht erneut bearbeitet. Qwen läuft mit `-s` im macOS Seatbelt-Sandboxmodus. Die Konfiguration setzt standardmäßig GitHub Auto-Merge auf `true`: GitHub führt den Merge erst nach erfüllten Branch Protection Rules und erforderlichen Checks aus. Externe PRs werden von diesem ersten Stand noch nicht bearbeitet.
