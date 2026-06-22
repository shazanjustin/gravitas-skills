#!/usr/bin/env python3
"""
Datasheet-to-GSheet Mapper — Column Mapping & CSV Generation Script

This script maps columns from a raw social media analytics CSV (e.g. Metricool export)
to a Google Sheet's column structure, producing a ready-to-paste CSV file.

Usage:
    python map_columns.py \
        --raw-csv "path/to/raw.csv" \
        --visible-columns "Col1,Col2,Col3,..." \
        --column-map "SheetCol1=RawCol1,SheetCol2=RawCol2,..." \
        --output "path/to/output.csv"

    python map_columns.py \
        --raw-csv "path/to/raw.csv" \
        --visible-columns-file "path/to/visible_columns.txt" \
        --column-map-file "path/to/column_map.txt" \
        --output "path/to/output.csv"

Arguments:
    --raw-csv           Path to the raw CSV file (Metricool export)
    --visible-columns   Comma-separated list of visible column names from Google Sheet
    --visible-columns-file  Path to a file containing visible columns (one per line)
    --column-map        Comma-separated key=value pairs: GoogleSheetCol=RawCSVCol
    --column-map-file   Path to a file containing column mappings (one per line, format: SheetCol=RawCol)
    --output            Path to save the output CSV
    --keep-summary      If set, keeps summary/aggregate rows at the bottom
    --encoding          Encoding of the raw CSV file (default: utf-8-sig)
"""

import csv
import sys
import os
import argparse
import re


def normalize_column_name(name: str) -> str:
    """Normalize a column name for comparison purposes."""
    name = name.strip().lower()
    # Remove parenthetical content for comparison
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name)
    return name


def is_plural_match(name1: str, name2: str) -> bool:
    """Check if two names differ only by plural 's'."""
    n1, n2 = normalize_column_name(name1), normalize_column_name(name2)
    if n1 == n2:
        return True
    if n1 + 's' == n2 or n2 + 's' == n1:
        return True
    return False


def smart_match_columns(sheet_columns: list, raw_columns: list) -> dict:
    """
    Attempt to automatically match Google Sheet columns to raw CSV columns
    using intelligent heuristics.

    Returns a dict: { sheet_column_name: raw_column_name }
    """
    mapping = {}
    used_raw = set()

    # Normalize raw columns for lookup
    raw_normalized = {normalize_column_name(col): col for col in raw_columns}

    # Known synonyms: sheet_name -> possible raw names
    synonyms = {
        'post name': ['title'],
        'post date': ['date'],
        'publish time': ['publish time'],
        'total reach': ['reach', 'total reach'],
        'total views': ['views', 'total views'],
        'total like': ['likes', 'like', 'total like', 'total likes'],
        'total comment': ['comments', 'comment', 'total comment', 'total comments'],
        'total share': ['shares', 'share', 'total share', 'total shares'],
        'total save': ['saves', 'save', 'total save', 'total saves'],
        'total engagement': ['e', 'engagement', 'total engagement'],
        'total engagement %': ['engagement rate', 'er', 'total engagement %'],
        'follow': ['follows', 'follow'],
        'duration (secs)': ['duration (sec)', 'duration (secs)', 'duration'],
        'seconds viewed': ['seconds viewed'],
        'avg. seconds viewed': ['avg. seconds viewed', 'average seconds viewed'],
        'link click': ['link clicks', 'link click'],
        'watch time': ['watch time'],
        'average watch time': ['average watch time', 'avg watch time'],
        'minutes viewed': ['minutes viewed'],
        'avg. minutes viewed': ['avg. minutes viewed', 'average minutes viewed'],
        'clicks to play': ['clicks to play'],
    }

    for sheet_col in sheet_columns:
        if sheet_col in mapping:
            continue

        sheet_norm = normalize_column_name(sheet_col)

        # 1. Exact match (case-insensitive)
        if sheet_norm in raw_normalized and raw_normalized[sheet_norm] not in used_raw:
            mapping[sheet_col] = raw_normalized[sheet_norm]
            used_raw.add(raw_normalized[sheet_norm])
            continue

        # 2. Known synonym match
        matched = False
        if sheet_norm in synonyms:
            for syn in synonyms[sheet_norm]:
                syn_norm = normalize_column_name(syn)
                if syn_norm in raw_normalized and raw_normalized[syn_norm] not in used_raw:
                    mapping[sheet_col] = raw_normalized[syn_norm]
                    used_raw.add(raw_normalized[syn_norm])
                    matched = True
                    break
        if matched:
            continue

        # 3. Plural/singular match
        for raw_col in raw_columns:
            if raw_col in used_raw:
                continue
            if is_plural_match(sheet_col, raw_col):
                mapping[sheet_col] = raw_col
                used_raw.add(raw_col)
                matched = True
                break
        if matched:
            continue

        # 4. "Total X" matches "X" (strip "Total " prefix from sheet)
        if sheet_norm.startswith('total '):
            stripped = sheet_norm[6:]  # Remove "Total "
            if stripped in raw_normalized and raw_normalized[stripped] not in used_raw:
                mapping[sheet_col] = raw_normalized[stripped]
                used_raw.add(raw_normalized[stripped])
                continue
            # Try plural
            if stripped + 's' in raw_normalized and raw_normalized[stripped + 's'] not in used_raw:
                mapping[sheet_col] = raw_normalized[stripped + 's']
                used_raw.add(raw_normalized[stripped + 's'])
                continue

        # 5. No match found → will be empty column

    return mapping


def is_summary_row(row: dict, id_column: str, total_columns: int) -> bool:
    """
    Detect if a row is a summary/aggregate row that should be excluded.

    Summary rows typically have:
    - Empty identifying fields (Post ID, etc.)
    - Only a few numeric values (totals or rates)
    """
    id_val = row.get(id_column, '').strip() if id_column else ''

    if id_val:
        return False  # Has an ID, not a summary row

    # Count non-empty values
    non_empty = sum(1 for v in row.values() if v.strip())

    # If very few fields are filled, it's likely a summary row
    if non_empty <= max(3, total_columns * 0.15):
        return True

    return False


def map_and_generate_csv(
    raw_csv_path: str,
    visible_columns: list,
    column_map: dict,
    output_path: str,
    skip_summary_rows: bool = True,
    encoding: str = 'utf-8-sig',
    auto_match: bool = False
):
    """
    Read a raw CSV, map its columns to the Google Sheet structure,
    and output a ready-to-copy CSV.

    Args:
        raw_csv_path: Path to the raw Metricool CSV export
        visible_columns: List of visible column names from Google Sheet (in order)
        column_map: Dict mapping Google Sheet column name → raw CSV column name.
                    If empty and auto_match is True, will attempt smart matching.
        output_path: Path to save the output CSV
        skip_summary_rows: Whether to skip summary/aggregate rows at the bottom
        encoding: Encoding of the raw CSV file
        auto_match: If True and column_map is empty, attempt automatic matching
    """
    # Read raw CSV
    try:
        with open(raw_csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            raw_headers = reader.fieldnames
            raw_rows = list(reader)
    except UnicodeDecodeError:
        # Fallback to latin-1
        with open(raw_csv_path, 'r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            raw_headers = reader.fieldnames
            raw_rows = list(reader)

    if not raw_headers:
        print(f"ERROR: Could not read headers from {raw_csv_path}")
        sys.exit(1)

    print(f"Raw CSV: {raw_csv_path}")
    print(f"  Raw columns ({len(raw_headers)}): {', '.join(raw_headers)}")
    print(f"  Raw rows: {len(raw_rows)}")
    print()

    # Auto-match if no mapping provided
    if auto_match and not column_map:
        column_map = smart_match_columns(visible_columns, raw_headers)
        print(f"Auto-matched {len(column_map)} columns:")
        for sheet_col, raw_col in column_map.items():
            print(f"  '{sheet_col}' <- '{raw_col}'")
        print()

    # Identify which columns have no mapping
    empty_columns = [col for col in visible_columns if col not in column_map]
    if empty_columns:
        print(f"Columns with no mapping (will be empty): {', '.join(empty_columns)}")
        print()

    # Get ID column for summary row detection
    id_col = raw_headers[0] if raw_headers else None

    # Filter out summary rows
    data_rows = []
    skipped_rows = 0
    for row in raw_rows:
        if skip_summary_rows and is_summary_row(row, id_col, len(raw_headers)):
            skipped_rows += 1
            continue
        data_rows.append(row)

    if skipped_rows > 0:
        print(f"Skipped {skipped_rows} summary/aggregate rows")

    # Generate output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(visible_columns)

        # Write data rows
        for row in data_rows:
            out_row = []
            for col in visible_columns:
                if col in column_map:
                    raw_col = column_map[col]
                    out_row.append(row.get(raw_col, ''))
                else:
                    out_row.append('')  # No mapping → empty
            writer.writerow(out_row)

    print(f"\n[SUCCESS] File successfully saved to {output_path}")
    print(f"   Columns: {len(visible_columns)}")
    print(f"   Data rows: {len(data_rows)}")
    print(f"   Mapped columns: {len(column_map)}")
    print(f"   Empty columns: {len(empty_columns)}")


def parse_column_map(map_str: str) -> dict:
    """Parse a column map string like 'SheetCol1=RawCol1,SheetCol2=RawCol2'"""
    if not map_str:
        return {}
    mapping = {}
    for pair in map_str.split(','):
        if '=' in pair:
            key, value = pair.split('=', 1)
            mapping[key.strip()] = value.strip()
    return mapping


def read_columns_from_file(filepath: str) -> list:
    """Read column names from a file (one per line)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def read_map_from_file(filepath: str) -> dict:
    """Read column mappings from a file (one per line, format: SheetCol=RawCol)."""
    mapping = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line:
                key, value = line.split('=', 1)
                mapping[key.strip()] = value.strip()
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description='Map raw CSV columns to Google Sheet structure and generate ready-to-copy CSV'
    )
    parser.add_argument('--raw-csv', required=True, help='Path to the raw CSV file')
    parser.add_argument('--visible-columns', help='Comma-separated visible column names')
    parser.add_argument('--visible-columns-file', help='File containing visible columns (one per line)')
    parser.add_argument('--column-map', help='Column mappings as SheetCol=RawCol pairs, comma-separated')
    parser.add_argument('--column-map-file', help='File containing column mappings (one per line)')
    parser.add_argument('--output', required=True, help='Output CSV path')
    parser.add_argument('--keep-summary', action='store_true', help='Keep summary rows')
    parser.add_argument('--auto-match', action='store_true', help='Auto-match columns using heuristics')
    parser.add_argument('--encoding', default='utf-8-sig', help='Raw CSV encoding')

    args = parser.parse_args()

    # Get visible columns
    if args.visible_columns_file:
        visible_columns = read_columns_from_file(args.visible_columns_file)
    elif args.visible_columns:
        visible_columns = [c.strip() for c in args.visible_columns.split(',')]
    else:
        print("ERROR: Must provide either --visible-columns or --visible-columns-file")
        sys.exit(1)

    # Get column map
    if args.column_map_file:
        column_map = read_map_from_file(args.column_map_file)
    elif args.column_map:
        column_map = parse_column_map(args.column_map)
    else:
        column_map = {}

    map_and_generate_csv(
        raw_csv_path=args.raw_csv,
        visible_columns=visible_columns,
        column_map=column_map,
        output_path=args.output,
        skip_summary_rows=not args.keep_summary,
        encoding=args.encoding,
        auto_match=args.auto_match or not column_map
    )


if __name__ == '__main__':
    main()
