#!/usr/bin/env python3
"""Timed documentation governance sweep.

This script enforces review cadence for key documentation files using a
structured registry at docs/governance/doc_review_registry.json.

Usage:
    python -m scripts.docs_review_sweep
    python -m scripts.docs_review_sweep --warn-days 14
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "docs" / "governance" / "doc_review_registry.json"


@dataclass
class ReviewItem:
    path: str
    owner: str
    cadence_days: int
    last_reviewed: date


@dataclass
class SweepResult:
    errors: list[str]
    warnings: list[str]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _load_registry() -> list[ReviewItem]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"missing registry file: {REGISTRY_PATH}")

    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("registry must be a JSON array")

    items: list[ReviewItem] = []
    for idx, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"registry item #{idx} must be an object")

        required = {"path", "owner", "cadence_days", "last_reviewed"}
        missing = required - set(row.keys())
        if missing:
            raise ValueError(f"registry item #{idx} missing keys: {sorted(missing)}")

        cadence_days = int(row["cadence_days"])
        if cadence_days <= 0:
            raise ValueError(f"registry item #{idx} cadence_days must be > 0")

        items.append(
            ReviewItem(
                path=str(row["path"]),
                owner=str(row["owner"]),
                cadence_days=cadence_days,
                last_reviewed=_parse_date(str(row["last_reviewed"])),
            )
        )

    return items


def run_sweep(items: list[ReviewItem], warn_days: int) -> SweepResult:
    today = date.today()
    warnings: list[str] = []
    errors: list[str] = []

    for item in items:
        doc_path = ROOT / item.path
        if not doc_path.exists():
            errors.append(f"missing governed document: {item.path}")
            continue

        if item.last_reviewed > today:
            errors.append(
                f"last_reviewed is in the future for {item.path}: {item.last_reviewed.isoformat()}"
            )
            continue

        due_date = item.last_reviewed + timedelta(days=item.cadence_days)
        days_left = (due_date - today).days

        if days_left < 0:
            errors.append(
                f"overdue review: {item.path} (owner={item.owner}, due={due_date.isoformat()}, {abs(days_left)} days late)"
            )
        elif days_left <= warn_days:
            warnings.append(
                f"review due soon: {item.path} (owner={item.owner}, due={due_date.isoformat()}, {days_left} days left)"
            )

    return SweepResult(errors=errors, warnings=warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run timed docs governance sweep")
    parser.add_argument(
        "--warn-days",
        type=int,
        default=14,
        help="days before due date to print warning (default: 14)",
    )
    args = parser.parse_args()

    try:
        items = _load_registry()
    except Exception as exc:
        print(f"docs review sweep setup error: {exc}")
        return 2

    result = run_sweep(items=items, warn_days=max(args.warn_days, 0))

    if result.warnings:
        print("docs review sweep warnings:")
        for msg in result.warnings:
            print(f"- {msg}")

    if result.errors:
        print("docs review sweep failed:")
        for msg in result.errors:
            print(f"- {msg}")
        return 1

    print("docs review sweep passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
