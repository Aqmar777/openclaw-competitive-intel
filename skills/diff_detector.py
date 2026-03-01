#!/usr/bin/env python3
"""
Skill: Diff Detector
Compare two snapshots and extract what changed.

Usage:
  python3 diff_detector.py --id manus --label "Product Updates"
  python3 diff_detector.py --file-old old.json --file-new new.json
"""

import os
import sys
import json
import re
import difflib
import argparse
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "snapshots")


def get_snapshots(competitor_id, monitor_label, count=2):
    """Get the N most recent snapshots for a monitor."""
    snap_dir = os.path.join(DATA_DIR, competitor_id)
    if not os.path.exists(snap_dir):
        return []

    safe_label = re.sub(r'[^\w\-]', '_', monitor_label.lower())
    files = sorted([
        f for f in os.listdir(snap_dir)
        if f.startswith(safe_label) and f.endswith(".json")
    ])

    results = []
    for f in files[-count:]:
        path = os.path.join(snap_dir, f)
        with open(path, "r", encoding="utf-8") as fh:
            results.append(json.load(fh))

    return results


def compute_diff(old_text, new_text, context_lines=3):
    """Compute a human-readable diff between two texts."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="previous", tofile="current",
        lineterm="", n=context_lines
    )

    return list(diff)


def extract_changes(old_text, new_text, threshold=50):
    """Extract structured change summary.
    
    Returns:
        dict with added/removed/modified sections
    """
    old_lines = set(old_text.splitlines())
    new_lines = set(new_text.splitlines())

    added_lines = new_lines - old_lines
    removed_lines = old_lines - new_lines

    # Filter out trivial changes (whitespace, very short lines)
    added = [l.strip() for l in added_lines if len(l.strip()) > 10]
    removed = [l.strip() for l in removed_lines if len(l.strip()) > 10]

    # Calculate change magnitude
    old_len = len(old_text)
    new_len = len(new_text)
    change_ratio = abs(new_len - old_len) / max(old_len, 1)

    # Determine change type
    if len(added) > 0 and len(removed) == 0:
        change_type = "content_added"
    elif len(added) == 0 and len(removed) > 0:
        change_type = "content_removed"
    elif len(added) > 0 and len(removed) > 0:
        change_type = "content_modified"
    else:
        change_type = "no_significant_change"

    # Severity
    if change_ratio > 0.3 or len(added) + len(removed) > 20:
        severity = "major"
    elif change_ratio > 0.1 or len(added) + len(removed) > 5:
        severity = "moderate"
    elif len(added) + len(removed) > 0:
        severity = "minor"
    else:
        severity = "none"

    return {
        "change_type": change_type,
        "severity": severity,
        "change_ratio": round(change_ratio, 4),
        "lines_added": len(added),
        "lines_removed": len(removed),
        "added_content": added[:30],  # Cap at 30 for readability
        "removed_content": removed[:30],
        "old_length": old_len,
        "new_length": new_len
    }


def detect_changes(competitor_id, monitor_label):
    """Main entry: compare latest two snapshots and return changes."""
    snapshots = get_snapshots(competitor_id, monitor_label, count=2)

    if len(snapshots) < 2:
        return {
            "competitor_id": competitor_id,
            "monitor_label": monitor_label,
            "status": "insufficient_data",
            "message": f"Need at least 2 snapshots. Have {len(snapshots)}.",
            "snapshots_available": len(snapshots)
        }

    old_snap = snapshots[0]
    new_snap = snapshots[1]

    # Quick hash check
    if old_snap["content_hash"] == new_snap["content_hash"]:
        return {
            "competitor_id": competitor_id,
            "monitor_label": monitor_label,
            "status": "no_change",
            "old_fetched_at": old_snap["fetched_at"],
            "new_fetched_at": new_snap["fetched_at"]
        }

    # Compute detailed diff
    changes = extract_changes(old_snap["content"], new_snap["content"])
    diff_lines = compute_diff(old_snap["content"], new_snap["content"])

    return {
        "competitor_id": competitor_id,
        "monitor_label": monitor_label,
        "url": new_snap.get("url", ""),
        "status": "changed",
        "old_fetched_at": old_snap["fetched_at"],
        "new_fetched_at": new_snap["fetched_at"],
        "changes": changes,
        "diff_preview": "\n".join(diff_lines[:100]),  # First 100 lines of diff
        "old_content": old_snap["content"][:3000],
        "new_content": new_snap["content"][:3000]
    }


def main():
    parser = argparse.ArgumentParser(description="Detect changes between snapshots")
    parser.add_argument("--id", help="Competitor ID")
    parser.add_argument("--label", help="Monitor label")
    parser.add_argument("--file-old", help="Old snapshot JSON file")
    parser.add_argument("--file-new", help="New snapshot JSON file")
    args = parser.parse_args()

    if args.file_old and args.file_new:
        with open(args.file_old) as f:
            old = json.load(f)
        with open(args.file_new) as f:
            new = json.load(f)
        changes = extract_changes(old["content"], new["content"])
        print(json.dumps(changes, indent=2, ensure_ascii=False))
    elif args.id and args.label:
        result = detect_changes(args.id, args.label)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Provide --id + --label, or --file-old + --file-new")
        sys.exit(1)


if __name__ == "__main__":
    main()
