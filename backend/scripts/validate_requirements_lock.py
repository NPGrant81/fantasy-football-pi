#!/usr/bin/env python3
"""Validate backend requirements and lock-file hygiene.

Checks performed (default mode):
1) Detect duplicate direct dependency declarations in requirements.txt.
2) Detect conflicting version pins for same package name.
3) Ensure requirements entries are pinned with `==`.
4) Validate lock file parseability and detect duplicate/conflicting pins.

Optional strict mode (`--strict-lock`) also enforces that each direct pinned
dependency in requirements.txt exists in requirements-lock.txt with the same
version.

This script is intentionally lightweight and uses only the standard library,
so it can run before installing project dependencies in CI.
"""

from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = ROOT / "requirements.txt"
LOCK_FILE = ROOT / "requirements-lock.txt"

PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*==\s*([^\s]+)$")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def clean_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""
    if line.startswith(("-r", "--", "-e", "git+")):
        return ""

    # remove inline comments and environment markers for parsing core pin
    line = line.split("#", 1)[0].strip()
    line = line.split(";", 1)[0].strip()
    return line


def parse_pins(path: Path) -> tuple[dict[str, tuple[str, int, str]], list[str]]:
    errors: list[str] = []
    pins: dict[str, tuple[str, int, str]] = {}

    if not path.exists():
        return pins, [f"Missing file: {path}"]

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = clean_line(raw)
        if not line:
            continue

        match = PIN_RE.match(line)
        if not match:
            errors.append(
                f"{path.name}:{line_no} must be pinned with == (found: {raw.strip()})"
            )
            continue

        pkg_name, version = match.group(1), match.group(2)
        key = normalize_name(pkg_name)

        if key in pins:
            existing_version, existing_line, existing_name = pins[key]
            if existing_version != version:
                errors.append(
                    f"Conflicting pins for {key}: "
                    f"{existing_name}=={existing_version} (line {existing_line}) vs "
                    f"{pkg_name}=={version} (line {line_no})"
                )
            else:
                errors.append(
                    f"Duplicate pin for {key}: {pkg_name}=={version} already defined at line {existing_line}"
                )
            continue

        pins[key] = (version, line_no, pkg_name)

    return pins, errors


def validate_lock_sync(strict_lock: bool = False) -> int:
    req_pins, req_errors = parse_pins(REQ_FILE)
    lock_pins, lock_errors = parse_pins(LOCK_FILE)

    errors = [*req_errors, *lock_errors]

    if strict_lock:
        for pkg, (req_version, req_line, req_name) in req_pins.items():
            lock_entry = lock_pins.get(pkg)
            if not lock_entry:
                errors.append(
                    f"{req_name}=={req_version} (requirements.txt:{req_line}) missing from requirements-lock.txt"
                )
                continue

            lock_version, lock_line, lock_name = lock_entry
            if lock_version != req_version:
                errors.append(
                    f"Version mismatch for {pkg}: requirements.txt has {req_name}=={req_version} "
                    f"(line {req_line}) but requirements-lock.txt has {lock_name}=={lock_version} "
                    f"(line {lock_line})"
                )

    if errors:
        print("❌ Dependency lock validation failed:\n")
        for issue in errors:
            print(f" - {issue}")
        print("\nFix by updating backend/requirements.txt and regenerating backend/requirements-lock.txt")
        return 1

    mode = "strict" if strict_lock else "standard"
    print(
        f"✅ Dependency validation ({mode} mode) passed for {len(req_pins)} direct requirements "
        f"and {len(lock_pins)} lock entries"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate requirements and lock consistency")
    parser.add_argument(
        "--strict-lock",
        action="store_true",
        help="enforce exact requirements.txt to requirements-lock.txt version sync",
    )
    args = parser.parse_args()
    sys.exit(validate_lock_sync(strict_lock=args.strict_lock))
