#!/usr/bin/env python3
"""Quick viewer for structured chat logs."""

import argparse
import json
import os
from glob import glob

# pyrefly: ignore [missing-import]
from config import Config


def _chat_log_files():
    files = [Config.CHAT_LOG_FILE]
    files.extend(sorted(glob(f"{Config.CHAT_LOG_FILE}.*"), reverse=True))
    return [path for path in files if os.path.isfile(path)]


def _load_entries(limit=None, session_id=None):
    entries = []
    for path in _chat_log_files():
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if session_id and entry.get("session_id") != session_id:
                    continue
                entries.append(entry)
    entries.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    if limit is not None:
        entries = entries[:limit]
    return entries


def main():
    parser = argparse.ArgumentParser(description="View CKPCMC chat logs")
    parser.add_argument("--last", type=int, default=20, help="Show the most recent N chats")
    parser.add_argument("--session", help="Filter by session ID")
    parser.add_argument("--json", action="store_true", help="Print raw JSON lines")
    args = parser.parse_args()

    entries = _load_entries(limit=args.last, session_id=args.session)
    if not entries:
        print("No chat logs found.")
        return

    if args.json:
        for entry in reversed(entries):
            print(json.dumps(entry, ensure_ascii=False))
        return

    for entry in reversed(entries):
        print("-" * 72)
        print(f"{entry.get('timestamp', 'unknown')} | session: {entry.get('session_id', 'n/a')}")
        print(f"Query: {entry.get('query', '')}")
        print(f"Response: {entry.get('response', '')}")
        print(
            f"Timing: retrieval {entry.get('retrieval_s', 0)}s | "
            f"generation {entry.get('generation_s', 0)}s"
        )


if __name__ == "__main__":
    main()
