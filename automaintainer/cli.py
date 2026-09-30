from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_config, load_env_file
from .runner import Runner


def main() -> None:
    parser = argparse.ArgumentParser(prog="automaintainer")
    parser.add_argument("--config", default="config.toml")
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="poll Jira and run due maintenance scans")
    run.add_argument("--dry-run", action="store_true")
    ticket = sub.add_parser("ticket", help="process one Jira ticket")
    ticket.add_argument("key")
    ticket.add_argument("--dry-run", action="store_true")
    sub.add_parser("escalations", help="show unresolved local escalations")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    load_env_file(config_path.parent / ".env")
    cfg = load_config(config_path)
    runner = Runner(cfg)
    try:
        if args.action == "escalations":
            print(json.dumps(runner.escalations(), indent=2))
        elif args.action == "ticket":
            print(json.dumps(runner.process_ticket(args.key, dry_run=args.dry_run), indent=2))
        else:
            print(json.dumps(runner.run(dry_run=args.dry_run), indent=2))
    except Exception as exc:
        print(f"automaintainer: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
