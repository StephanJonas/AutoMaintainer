# AutoMaintainer

Lokaler Wartungsdienst für Jira-Bugs und GitHub-Pull-Requests. Qwen Code bearbeitet ein Ticket ausschließlich in einem kurzlebigen Git-Worktree. Der Orchestrator erzwingt anschließend Dateiregeln, Tests und Scanner, bevor er einen Pull Request erstellt oder aktualisiert. Zugangsdaten werden aus der Umgebung gelesen.

## Sicherheitsmodell

- `protected_paths` sind nach dem Agentenlauf unveränderlich. Änderungen dort verwerfen den gesamten Lauf.
- Der Agent darf nur in seinem Wegwerf-Worktree schreiben. Er kann weder direkt auf den Zielbranch pushen noch mergen.
- Ein sauberer Patch muss außerhalb geschützter Pfade liegen, das konfigurierte Diff-Limit einhalten und alle Tests/Scanner bestehen.
- Nur der Orchestrator veröffentlicht einen PR und aktiviert optional GitHub Auto-Merge. Branchschutz und erforderliche CI-Checks müssen im Repository konfiguriert sein.
- Ein fehlgeschlagener oder mehrdeutiger Lauf wird in Jira kommentiert und dem konfigurierten Eskalationsbenutzer zugewiesen; er wird nicht gemergt.
- Das Modell prüft nicht seine eigene Sicherheit. Git-Diff-Regeln und Prüfkommandos entscheiden.

Auto-Merge kann nur sicher sein, wenn GitHub Branch Protection, erforderliche Statuschecks und mindestens ein geschützter Zielbranch eingerichtet sind. Der Bot bekommt nur die minimal nötigen Jira- und GitHub-Rechte. Release-Branches gehören nicht als `base_branch` in die Konfiguration.

## Voraussetzungen

- macOS, Python 3.11+, Git, Ollama, Qwen Code CLI (`qwen`) und GitHub CLI (`gh`).
- Qwen Code auf denselben lokalen Ollama-Modellnamen konfigurieren. Der Agent nutzt `qwen --prompt` im Repo-Worktree; die Provider-Konfiguration liegt in `~/.qwen/settings.json`.
- `gh auth login` mit Repo-Rechten für Branch/PR-Erstellung und Auto-Merge.
- Jira Cloud API-Token. Das Jira-Konto braucht Rechte zum Hinzufügen von Kommentaren und Zuweisen der Tickets. Für Jira Data Center muss der Jira-Adapter angepasst werden.
- Ollama läuft lokal; `ollama_model` muss installiert sein. Derselbe lokale Modellname sollte auch im Qwen-Code-Provider ausgewählt sein.

## Einrichtung

```sh
cd ~/Development/AutoMaintainer
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp config.example.toml config.toml
cp .env.example .env
chmod 600 .env
```

`config.toml` auf deine Jira-Projekte und Repositories, geschützte Pfade, Test- und Scan-Kommandos sowie `jira.escalation_assignee_account_id` anpassen. Die Konfiguration ist nach Jira-Projekt gruppiert: Jeder `[[projects]]`-Block steht für ein Jira-Projekt; darunter stehen ein oder mehrere `[[projects.repos]]`-Blöcke für die zugehörigen Git-Repositories. Jira Cloud erwartet bei `escalation_assignee_account_id` die Atlassian accountId des Benutzers, der Eskalationen übernehmen soll. Datei und lokale State-Daten sind gitignored.

Bei genau einem Repository unter einem Jira-Projekt wird jedes passende unassigned Bug-Ticket diesem Repository zugeordnet. Bei mehreren Repositories muss jedes Repo eindeutige `jira_components` angeben. Die Namen müssen den Jira-Komponenten entsprechen, die im Ticket gesetzt sind. Nur wenn genau ein Repo über eine Komponente passt, wird das Ticket bearbeitet. Bei fehlender oder mehrdeutiger Zuordnung eskaliert der Maintainer in Jira, ohne ein Repository zu ändern. `issue_prefix` wird für den manuellen Befehl `automaintainer ticket KEY` verwendet und sollte zum Projektschlüssel passen.

`test_commands` laufen lokal im temporären Worktree vor einer PR-Erstellung. Sie können Unit-, Integrations- und E2E-Tests enthalten, auch wenn diese nicht in GitHub Actions laufen. Trage sie als einzelne Kommandos ein; jedes muss seine nötigen Dienste selbst starten oder eine passende Testkonfiguration verwenden. `required_checks` bezeichnet dagegen ausschließlich GitHub-Statuschecks für den Merge.

Technologiebezogene Modellprüfungen werden als wiederverwendbare `[security_profiles.NAME]` definiert. Ein Repo kann beliebig viele `[[projects.repos.security_targets]]` enthalten; jedes Ziel nennt einen eindeutigen Schlüssel, einen Pfad relativ zum Repo und ein Profil. Beim wöchentlichen Scan laufen die normalen `security_commands` einmal im Repo und zusätzlich eine lokale Ollama-Prüfung pro Ziel. Das Modell erhält versionierte Textdateien aus dem Ziel (maximal 100.000 Zeichen Quelltext); Secret-Dateien und Symlinks werden ausgelassen. Ist der Kontext zu groß, nicht vollständig lesbar oder die Antwort nicht eindeutig, gilt die Prüfung als eskaliert. Die Modellprüfung liest Dateien nur und meldet strukturierte Befunde; sie ändert nichts. Beispielprofile und Zielblöcke stehen auskommentiert in `config.example.toml`.

Automatische Dependency-Reparaturen sind ein eigener, standardmäßig deaktivierter Schritt. Aktiviere sie pro Repo mit `security_auto_remediate = true` und gib mit `dependency_paths` die erlaubten Manifest- und Lockdateien explizit frei, zum Beispiel `pyproject.toml` und `uv.lock`, oder `package.json` und `package-lock.json`. Bei einem Scanner- oder Profilbefund aus einer freigegebenen Dependency-Datei kann Qwen in einem wegwerfbaren Worktree einen minimalen Update-Vorschlag erstellen. Eine separate Ollama-Prüfung bewertet den Diff; eine feste Pfadregel sperrt Tests, E2E-Konfigurationen, CI und Policy-Dateien. Danach müssen alle lokalen `test_commands` und Security-Scanner bestehen. Erst dann wird ein Security-PR angelegt; bei `auto_merge = true` gelten zusätzlich die konfigurierten GitHub-Branchschutzregeln. Befunde, die kein klarer Dependency-Fix sind, fehlgeschlagene Prüfungen und bereits offene Security-PRs werden nicht automatisch geändert bzw. dupliziert.

Jira-Zugangsdaten in `.env` im selben Ordner wie `config.toml` eintragen:

```dotenv
JIRA_BASE_URL=https://example.atlassian.net
JIRA_EMAIL=maintainer@example.com
JIRA_API_TOKEN=...
```

Der CLI lädt diese Datei automatisch. Die Datei wird nicht als Shell-Skript ausgeführt; unterstützt werden einfache `KEY=value`-Zeilen, Kommentare und Werte in einfachen/doppelten Anführungszeichen. Bereits gesetzte Prozess-Umgebungsvariablen haben Vorrang. Der CLI verweigert den Start, wenn `.env` für Gruppe oder andere lesbar ist; `chmod 600 .env` setzt die nötigen Rechte. `.env` und `.env.*` sind gitignored, `.env.example` bleibt eingecheckt.

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

`launchd/com.local.automaintainer.plist.example` ist ein Beispiel für tägliche Ausführung. Der Dienst prüft anhand des lokalen Datums, ob der wöchentliche Scan fällig ist. Passe Benutzerpfade an und installiere es als `~/Library/LaunchAgents/com.local.automaintainer.plist`. Die CLI lädt `.env` relativ zum Config-Pfad auch unter launchd automatisch. Jobs laufen, wenn der Mac eingeschaltet ist; verpasste Läufe werden beim nächsten Start nachgeholt.

## Ablauf und Eskalationen

Logs und Status liegen unter `~/.local/state/automaintainer/`. Jeder Lauf speichert Ticket/PR, Branch, Basis-Commit, Diff-Prüfung, Test- und Scan-Ergebnisse sowie Eskalationsgrund. Der erste Stand erzeugt PRs und aktiviert Auto-Merge nach bestandenem CI, wenn `auto_merge = true`. Nicht erfolgreiche Arbeiten erhalten keinen PR; Eskalationsmeldungen erscheinen im lokalen Log und in `automaintainer escalations`.

Es werden nur Jira-Tickets vom Typ `Bug` berücksichtigt, deren Assignee leer ist. Vor Qwen Code beurteilt ein strukturierter Aufruf an den lokalen Ollama-Server, ob das Ticket einen belegten Fehler gegenüber bereits erwartetem Verhalten beschreibt. Nach dem Qwen-Aufruf prüft ein weiterer lokaler Ollama-Aufruf den Diff auf Funktionswünsche und Änderungen am beabsichtigten Verhalten. Nur eine klare Bug-Einstufung mit mindestens 0,85 Modellvertrauen an beiden Gates darf weiterlaufen; ein Jira-Ticket vom Typ Bug reicht allein nicht. Beide Modellentscheidungen bleiben heuristisch und sind keine formale Garantie.

Ein Ticket mit bereits erstelltem PR wird nicht erneut bearbeitet. Bei einer Eskalation wird der Grund als Jira-Kommentar hinterlegt und das Ticket dem konfigurierten Benutzer zugewiesen. Wiederholte Eskalationen mit demselben Grund erzeugen keinen doppelten Kommentar. Qwen läuft mit `-s` im macOS Seatbelt-Sandboxmodus.

Auch `automaintainer ticket KEY` prüft vor der Bearbeitung nochmals den Typ und die Zuweisung. Jira-Kommentare werden über die Cloud REST API v3 erstellt und Zuweisungen über die Assign-Issue-Operation gesetzt; das verwendete Jira-Konto benötigt die jeweiligen Projektberechtigungen. [Kommentar-API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/), [Issue-Zuweisung](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)

Der Root-`AGENTS.md`- und `SYSTEM.md`-Inhalt des Worktrees wird vor dem Qwen-Aufruf explizit in den Prompt eingefügt. So hängt die Übergabe nicht davon ab, ob Qwen Code diese Dateien von selbst erkennt. Fehlt eine Pflichtdatei, wird Qwen nicht gestartet und das Ticket stattdessen eskaliert. Diese Projektdateien ergänzen die Wartungsanweisung, können aber deren festen Schutzregeln nicht aufheben.

Die Konfiguration setzt standardmäßig GitHub Auto-Merge auf `true`: GitHub führt den Merge erst nach erfüllten Branch Protection Rules und erforderlichen Checks aus. Externe PRs werden von diesem ersten Stand noch nicht bearbeitet.
