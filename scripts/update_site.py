#!/usr/bin/env python3

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPDATES_DIR = ROOT / "updates"
MARKDOWN_FILE = ROOT / "exposome.md"
SELECTION_FILE = DATA_DIR / "selected-updates.json"
HISTORY_FILE = DATA_DIR / "monthly-updates.json"

UPDATES_START = "<!-- MONTHLY_UPDATES_START -->"
UPDATES_END = "<!-- MONTHLY_UPDATES_END -->"
ARCHIVE_START = "<!-- MONTHLY_ARCHIVE_START -->"
ARCHIVE_END = "<!-- MONTHLY_ARCHIVE_END -->"


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text())


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def validate_selection(data):
    """Validate that selection data has the expected structure."""
    required = ["month", "generated_at", "mode"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Selection file missing required keys: {missing}")
    if not isinstance(data.get("updates", []), list):
        raise ValueError("Selection 'updates' must be a list")
    if not isinstance(data.get("review_queue", []), list):
        raise ValueError("Selection 'review_queue' must be a list")
    return data


def render_latest_block(month_entry):
    month = month_entry["month"]
    lines = [f"### {month}", ""]
    updates = month_entry.get("updates", [])
    if updates:
        for update in updates:
            lines.append(
                f"- **[{update['title']}]({update['url']})** — {update['summary']}"
            )
    else:
        lines.append(
            "No new papers were auto-published this month. The workflow collected candidates, "
            "but no update passed automatic publication criteria."
        )
    lines.append("")
    return "\n".join(lines).strip()


def render_archive_block(history):
    if not history:
        return "- No monthly archives yet."
    lines = []
    for entry in sorted(history, key=lambda item: item["month"], reverse=True):
        html_path = f"updates/{entry['month']}.html"
        count = len(entry.get("updates", []))
        suffix = f"{count} published update{'s' if count != 1 else ''}"
        if count == 0:
            suffix = "no auto-published updates"
        lines.append(f"- [{entry['month']}]({html_path}) — {suffix}")
    return "\n".join(lines)


def replace_marker_block(text, start_marker, end_marker, replacement):
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S
    )
    block = f"{start_marker}\n{replacement}\n{end_marker}"
    if pattern.search(text):
        return pattern.sub(block, text)
    raise ValueError(f"Missing marker block: {start_marker} ... {end_marker}")


def write_month_archive(entry):
    month = entry["month"]
    updates = entry.get("updates", [])
    lines = [f"# {month} textbook-worthy updates", ""]
    lines.append(
        "This page is machine-generated from the monthly literature scan. "
        "Only items considered broad, textbook-relevant additions are published here."
    )
    lines.append("")
    if updates:
        for update in updates:
            lines.extend(
                [
                    f"## [{update['title']}]({update['url']})",
                    "",
                    update["summary"],
                    "",
                    f"**Why it matters:** {update['why_it_matters']}",
                    "",
                    f"**Suggested section:** {update['section']}",
                    "",
                ]
            )
    else:
        lines.append("No new papers were auto-published for this month.")
        lines.append("")
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = UPDATES_DIR / f"{month}.md"
    archive_path.write_text("\n".join(lines).rstrip() + "\n")


def main():
    selection = validate_selection(load_json(SELECTION_FILE))

    # Load history with graceful fallback for first run
    if HISTORY_FILE.exists():
        history = load_json(HISTORY_FILE)
    else:
        print(f"  History file not found, creating new one", file=sys.stderr)
        history = {"history": []}

    existing = {entry["month"]: entry for entry in history.get("history", [])}

    month_entry = {
        "month": selection["month"],
        "generated_at": selection["generated_at"],
        "mode": selection["mode"],
        "updates": selection.get("updates", []),
    }
    existing[month_entry["month"]] = month_entry
    new_history = {"history": [existing[key] for key in sorted(existing.keys())]}
    save_json(HISTORY_FILE, new_history)
    write_month_archive(month_entry)

    if not MARKDOWN_FILE.exists():
        raise FileNotFoundError(f"Main markdown file not found: {MARKDOWN_FILE}")

    markdown = MARKDOWN_FILE.read_text()
    markdown = replace_marker_block(
        markdown, UPDATES_START, UPDATES_END, render_latest_block(month_entry)
    )
    markdown = replace_marker_block(
        markdown,
        ARCHIVE_START,
        ARCHIVE_END,
        render_archive_block(new_history["history"]),
    )
    MARKDOWN_FILE.write_text(markdown)
    print(f"Updated {MARKDOWN_FILE} and archive for {month_entry['month']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"update_site.py failed: {exc}", file=sys.stderr)
        raise
