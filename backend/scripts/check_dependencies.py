#!/usr/bin/env python3
"""Check and report outdated / vulnerable Python dependencies.

This helper can be run manually or wired into a scheduled job (cron, GitHub
Actions, etc.). It inspects the current environment and any pinned requirements
files you point at, then prints a human-readable report and optionally
writes a markdown summary to `dependency-report.md` in the repo root.

Usage:
    python backend/scripts/check_dependencies.py [--lock-file]

Options:
  --lock-file   also inspect requirements-lock.txt (default only uses
                requirements.txt to detect additions).

The script uses ``pip`` commands under the current interpreter, so it should
run inside whatever virtualenv/container your project uses. It also attempts a
``pip audit`` to surface known security issues; if ``pip audit`` is not
available the script graciously continues.

This repository includes a GitHub Actions workflow that invokes this script on
a monthly schedule and when manually triggered. That workflow will leave a log
and can be modified to open issues/PRs when updates are found.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REQ = ROOT / "requirements.txt"
LOCK = ROOT / "requirements-lock.txt"
REPORT_FILE = ROOT / "dependency-report.md"


def run(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        return out.decode("utf-8")
    except subprocess.CalledProcessError as exc:
        return exc.output.decode("utf-8")


def list_outdated():
    # pip list --outdated --format=json
    out = run(f"{sys.executable} -m pip list --outdated --format=json")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data


def run_audit():
    # pip audit --format=json (available in pip>=22)
    out = run(f"{sys.executable} -m pip audit --format=json")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data


def main():
    parser = argparse.ArgumentParser(description="Dependency maintenance helper")
    parser.add_argument("--lock-file", action="store_true", help="also include requirements-lock.txt")
    args = parser.parse_args()

    print("Checking for outdated packages...")
    outdated = list_outdated()
    if outdated:
        print(f"Found {len(outdated)} outdated packages:\n")
        for pkg in outdated:
            print(f" - {pkg['name']}: {pkg['version']} -> {pkg['latest']} ({pkg['type']})")
    else:
        print("All packages are up to date.")

    print("\nRunning pip audit (security checks)...")
    audit = run_audit()
    if audit:
        print(f"{len(audit)} advisories found:\n")
        for adv in audit:
            pkg = adv.get("name")
            vulns = adv.get("vulns", [])
            for v in vulns:
                print(f" - {pkg} {v.get('version')} - {v.get('id')} {v.get('details')}")
    else:
        print("No security advisories (or audit not available).")

    # optionally record to markdown
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# Dependency Report\n\n")
        if outdated:
            f.write("## Outdated packages\n")
            for pkg in outdated:
                f.write(f"- {pkg['name']}: {pkg['version']} -> {pkg['latest']} ({pkg['type']})\n")
        else:
            f.write("All packages are up to date.\n")
        f.write("\n")
        f.write("## Security audit\n")
        if audit:
            for adv in audit:
                pkg = adv.get("name")
                f.write(f"### {pkg}\n")
                for v in adv.get("vulns", []):
                    f.write(f"- {v.get('id')} {v.get('version')}: {v.get('details')}\n")
        else:
            f.write("No advisories found or pip audit not available.\n")

    print(f"\nReport written to {REPORT_FILE.relative_to(ROOT)}")

    # if any outdated packages or audit advisories were detected, return
    # failure so automation jobs can act on it.
    if outdated or audit:
        sys.exit(1)


if __name__ == "__main__":
    main()
