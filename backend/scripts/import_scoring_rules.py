"""CSV importer/sanitizer for league scoring rules.

Usage:
    python import_scoring_rules.py path/to/file.csv

Reads a CSV with columns like Event,Range_Yds,Point_Value,PostionID and
outputs normalized JSON records to stdout (one per line).  Designed to help
commissioners bulk-load complex scoring rules.

The sanitizer handles Excel "Jan-99" style dates, normalizes ranges to numeric
min/max values, detects per-unit vs flat bonus rules, and maps provider numeric
position IDs to human-readable codes including FLEX.
"""

import csv
import json
import re
import sys

# month->number map used to fix Excel date coercion
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# provider position id -> human code (extend as needed)
POSITION_MAP = {
    '8002': 'QB',
    '8003': 'RB',
    '8004': 'WR',
    '8005': 'TE',
    '8006': 'DEF',
    '8099': 'K',
    '8010': 'FLEX',  # example flex id; add actual code if known
}


def sanitize_row(row):
    event = row.get('Event', '').strip()
    range_str = row.get('Range_Yds', '').strip().lower()
    point_str = row.get('Point_Value', '').strip().lower()
    pos_str = row.get('PostionID', '').strip()

    # --- range parsing ---
    min_val = 0
    max_val = 9999

    # check for Excel-style month-year mistakes
    date_match = re.match(r'([a-z]{3})-(\d+)', range_str)
    rev_date = re.match(r'(\d+)-([a-z]{3})', range_str)
    if date_match:
        mon, yr = date_match.groups()
        min_val = MONTH_MAP.get(mon, 0)
        max_val = int(yr)
    elif rev_date:
        lo, mon = rev_date.groups()
        min_val = int(lo)
        max_val = MONTH_MAP.get(mon, 0)
    elif '-' in range_str:
        parts = range_str.split('-')
        try:
            min_val = int(parts[0])
            max_val = int(parts[1])
        except ValueError:
            pass
    # ensure sensible ordering
    if min_val > max_val:
        min_val, max_val = max_val, min_val

    # --- calculation type & points ---
    is_per_unit = 'each' in point_str or 'per' in point_str
    try:
        points = float(re.sub(r'[^0-9.\-]', '', point_str))
    except ValueError:
        points = 0.0

    # --- positions ---
    positions = []
    for pid in re.split(r'[;,\s]+', pos_str):
        code = POSITION_MAP.get(pid.strip(), None)
        if code:
            positions.append(code)
        elif pid:
            positions.append(pid.strip())
    if not positions:
        positions = ['ALL']

    return {
        'event_name': event,
        'range_min': min_val,
        'range_max': max_val,
        'point_value': points,
        'calculation_type': 'per_unit' if is_per_unit else 'flat_bonus',
        'applicable_positions': positions,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python import_scoring_rules.py file.csv', file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    with open(path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            clean = sanitize_row(row)
            print(json.dumps(clean))


if __name__ == '__main__':
    main()
