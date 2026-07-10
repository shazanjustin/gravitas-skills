#!/usr/bin/env python3
"""
Datasheet-to-GSheet Mapper — Column Mapping & CSV Generation Script

Maps raw social media platform CSV exports (Facebook/Instagram) to the
Google Sheet column structure, producing ready-to-paste CSV files.

Improvements (v2):
  - FB Description: pulls from Title column first, falls back to Description
  - FB & IG Format: mapped from Post type column
  - Publish Time: full mm/dd/yyyy HH:MM datetime format (not time-only)
  - Rows sorted by Post Date ascending (oldest post first)

Usage:
    # FB
    python map_columns.py --platform fb --raw-csv "FB.csv" --output "FB_mapped.csv"

    # IG
    python map_columns.py --platform ig --raw-csv "IG.csv" --output "IG_mapped.csv"

    # Custom columns/mapping (advanced)
    python map_columns.py --raw-csv "raw.csv" --visible-columns "Col1,Col2,..." \
        --column-map "SheetCol1=RawCol1,..." --output "output.csv"
"""

import csv
import sys
import os
import argparse
import re
import datetime


# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM PRESETS
# ─────────────────────────────────────────────────────────────────────────────

HIDDEN = {
    "Industry", "Country", "Account Name", "Account ID",
    "Objective", "Start Date", "End Date", "Ad Duration",
}

FB_ALL_COLUMNS = [
    "Industry", "Country", "Account Name", "Account ID",
    "Post ID", "Permalink", "Year", "Quarter", "Campaign", "Organic/Paid",
    "Objective", "Start Date", "End Date", "Ad Duration",
    "Post Name", "Description", "Pillar", "Format", "Duration (secs)",
    "Post Date", "Publish Time",
    "Total Reach", "Organic Reach", "Paid Reach",
    "Total Views", "Organic Views", "Paid Views",
    "Total Like", "Organic Like", "Paid Like",
    "Total Comment", "Organic Comment", "Paid Comment",
    "Total Share", "Organic Share", "Paid Share",
    "Total Engagement", "Organic Engagement", "Paid Engagement",
    "Total Engagement %", "Organic Engagement %", "Paid Engagement %",
    "Watch Time", "Average Watch Time",
]

IG_ALL_COLUMNS = [
    "Industry", "Country", "Account Name", "Account ID",
    "Post ID", "Permalink", "Year", "Quarter", "Campaign", "Organic/Paid",
    "Objective", "Start Date", "End Date", "Ad Duration",
    "Post Name", "Description", "Pillar", "Format", "Duration (secs)",
    "Post Date", "Publish Time",
    "Total Reach", "Organic Reach", "Paid Reach",
    "Total Views", "Organic Views", "Paid Views",
    "Total Like", "Organic Like", "Paid Like",
    "Total Comment", "Organic Comment", "Paid Comment",
    "Total Share", "Organic Share", "Paid Share",
    "Total Save", "Organic Save", "Paid Save",
    "Total Engagement", "Organic Engagement", "Paid Engagement",
    "Total Engagement %", "Organic Engagement %", "Paid Engagement %",
    "Watch Time", "Average Watch Time", "Follow",
]

FB_VISIBLE_COLUMNS = [c for c in FB_ALL_COLUMNS if c not in HIDDEN]
IG_VISIBLE_COLUMNS = [c for c in IG_ALL_COLUMNS if c not in HIDDEN]

# Raw CSV column → GSheet column
# Note: Description and Format have special handling (see map_row_fb / map_row_ig)
FB_COLUMN_MAP = {
    "Post ID":                          "Post ID",
    "Permalink":                        "Permalink",
    "Publish time":                     "Publish Time",
    # Description → handled specially (Title first, then Description)
    # Format → handled specially (Post type)
    "Duration (sec)":                   "Duration (secs)",
    "Reach":                            "Total Reach",
    "Reach from Organic posts":         "Organic Reach",
    "Reach from Boosted posts":         "Paid Reach",
    "Views":                            "Total Views",
    "Views from Organic posts":         "Organic Views",
    "Views from Boosted posts":         "Paid Views",
    "Reactions":                        "Total Like",
    "Comments":                         "Total Comment",
    "Shares":                           "Total Share",
    "Reactions, comments and shares":   "Total Engagement",
    "Seconds viewed":                   "Watch Time",
    "Average Seconds viewed":           "Average Watch Time",
}

IG_COLUMN_MAP = {
    "Post ID":       "Post ID",
    "Permalink":     "Permalink",
    "Publish time":  "Publish Time",
    "Description":   "Description",
    # Format → handled specially (Post type)
    "Duration (sec)": "Duration (secs)",
    "Reach":         "Total Reach",
    "Views":         "Total Views",
    "Likes":         "Total Like",
    "Comments":      "Total Comment",
    "Shares":        "Total Share",
    "Saves":         "Total Save",
    "Follows":       "Follow",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

PUBLISH_TIME_FORMATS = (
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y",
    "%d-%b-%y %H:%M",
    "%b %d, %Y",
)


def parse_datetime(s: str):
    """Parse a datetime string into a datetime object, trying multiple formats."""
    s = s.strip()
    for fmt in PUBLISH_TIME_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def is_summary_row(row: dict, id_col: str = "Post ID") -> bool:
    """Return True if this row is a summary/aggregate row to skip."""
    v = row.get(id_col, "").strip()
    if not v:
        return True
    if any(kw in v.lower() for kw in ["total", "engagement", "rate", "er"]):
        return True
    # Post IDs are long numeric strings; short values are probably labels
    try:
        int(v)
        return False
    except ValueError:
        return len(v) <= 6


def normalize_column_name(name: str) -> str:
    """Normalize a column name for fuzzy comparison."""
    name = name.strip().lower()
    name = re.sub(r'\s*\(.*?\)\s*', ' ', name).strip()
    name = re.sub(r'\s+', ' ', name)
    return name


# ─────────────────────────────────────────────────────────────────────────────
# ROW MAPPING — PLATFORM-SPECIFIC
# ─────────────────────────────────────────────────────────────────────────────

def map_row_fb(raw_row: dict, vis_cols: list) -> tuple:
    """Map a single raw FB CSV row to GSheet visible columns. Returns (dt, out_dict)."""
    out = {c: "" for c in vis_cols}

    # Standard column mapping
    for raw_col, gs_col in FB_COLUMN_MAP.items():
        if raw_col in raw_row and gs_col in out:
            out[gs_col] = raw_row[raw_col]

    # Description: Title column first, fall back to Description
    title = raw_row.get("Title", "").strip()
    desc  = raw_row.get("Description", "").strip()
    out["Description"] = title if title else desc

    # Format: from Post type column
    out["Format"] = raw_row.get("Post type", "").strip()

    # Organic/Paid default
    if not out.get("Organic/Paid"):
        out["Organic/Paid"] = "Organic"

    # Publish Time → full mm/dd/yyyy HH:MM + derive Post Date, Year, Quarter
    dt = None
    pt = out.get("Publish Time", "").strip()
    if pt:
        dt = parse_datetime(pt)
        if dt:
            out["Publish Time"] = dt.strftime("%m/%d/%Y %H:%M")
            out["Post Date"]    = dt.strftime("%d/%m/%Y")
            out["Year"]         = str(dt.year)
            out["Quarter"]      = "Q{}".format((dt.month - 1) // 3 + 1)

    return dt, out


def map_row_ig(raw_row: dict, vis_cols: list) -> tuple:
    """Map a single raw IG CSV row to GSheet visible columns. Returns (dt, out_dict)."""
    out = {c: "" for c in vis_cols}

    # Standard column mapping
    for raw_col, gs_col in IG_COLUMN_MAP.items():
        if raw_col in raw_row and gs_col in out:
            out[gs_col] = raw_row[raw_col]

    # Format: from Post type column
    out["Format"] = raw_row.get("Post type", "").strip()

    # Organic/Paid default
    if not out.get("Organic/Paid"):
        out["Organic/Paid"] = "Organic"

    # Publish Time → full mm/dd/yyyy HH:MM + derive Post Date, Year, Quarter
    dt = None
    pt = out.get("Publish Time", "").strip()
    if pt:
        dt = parse_datetime(pt)
        if dt:
            out["Publish Time"] = dt.strftime("%m/%d/%Y %H:%M")
            out["Post Date"]    = dt.strftime("%d/%m/%Y")
            out["Year"]         = str(dt.year)
            out["Quarter"]      = "Q{}".format((dt.month - 1) // 3 + 1)

    return dt, out


# ─────────────────────────────────────────────────────────────────────────────
# SMART AUTO-MATCH (for custom / advanced usage)
# ─────────────────────────────────────────────────────────────────────────────

SYNONYMS = {
    'description':      ['title', 'description', 'caption'],
    'format':           ['post type', 'content type', 'media type'],
    'post date':        ['date', 'post date'],
    'publish time':     ['publish time', 'published at'],
    'total reach':      ['reach', 'total reach'],
    'total views':      ['views', 'total views', 'video views'],
    'total like':       ['likes', 'like', 'total like', 'total likes', 'reactions'],
    'total comment':    ['comments', 'comment', 'total comment', 'total comments'],
    'total share':      ['shares', 'share', 'total share', 'total shares'],
    'total save':       ['saves', 'save', 'total save', 'total saves'],
    'total engagement': ['engagement', 'total engagement', 'reactions, comments and shares'],
    'follow':           ['follows', 'follow'],
    'duration (secs)':  ['duration (sec)', 'duration (secs)', 'duration'],
    'watch time':       ['seconds viewed', 'watch time'],
    'average watch time': ['average seconds viewed', 'avg. seconds viewed', 'average watch time'],
    'organic reach':    ['reach from organic posts', 'organic reach'],
    'paid reach':       ['reach from boosted posts', 'paid reach'],
    'organic views':    ['views from organic posts', 'organic views'],
    'paid views':       ['views from boosted posts', 'paid views'],
}


def smart_match_columns(sheet_columns: list, raw_columns: list) -> dict:
    """Auto-match GSheet column names to raw CSV column names using heuristics."""
    mapping = {}
    used_raw = set()
    raw_normalized = {normalize_column_name(c): c for c in raw_columns}

    for sheet_col in sheet_columns:
        sheet_norm = normalize_column_name(sheet_col)

        # 1. Exact match
        if sheet_norm in raw_normalized and raw_normalized[sheet_norm] not in used_raw:
            mapping[sheet_col] = raw_normalized[sheet_norm]
            used_raw.add(raw_normalized[sheet_norm])
            continue

        # 2. Synonym match
        matched = False
        if sheet_norm in SYNONYMS:
            for syn in SYNONYMS[sheet_norm]:
                syn_norm = normalize_column_name(syn)
                if syn_norm in raw_normalized and raw_normalized[syn_norm] not in used_raw:
                    mapping[sheet_col] = raw_normalized[syn_norm]
                    used_raw.add(raw_normalized[syn_norm])
                    matched = True
                    break
        if matched:
            continue

        # 3. "Total X" strips prefix
        if sheet_norm.startswith("total "):
            stripped = sheet_norm[6:]
            for candidate in (stripped, stripped + "s"):
                if candidate in raw_normalized and raw_normalized[candidate] not in used_raw:
                    mapping[sheet_col] = raw_normalized[candidate]
                    used_raw.add(raw_normalized[candidate])
                    matched = True
                    break
        if matched:
            continue

    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# CORE PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def read_csv(path: str, encoding: str = "utf-8-sig") -> tuple:
    """Read a CSV file and return (headers, rows)."""
    try:
        with open(path, "r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1", newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    return headers, rows


def process_platform(
    raw_csv_path: str,
    output_path: str,
    platform: str,
    encoding: str = "utf-8-sig",
):
    """Process a single platform CSV using the built-in preset rules."""
    headers, raw_rows = read_csv(raw_csv_path, encoding)
    print("Input : {} ({} rows, {} columns)".format(raw_csv_path, len(raw_rows), len(headers)))

    if platform.lower() == "fb":
        vis_cols  = FB_VISIBLE_COLUMNS
        map_fn    = map_row_fb
    elif platform.lower() == "ig":
        vis_cols  = IG_VISIBLE_COLUMNS
        map_fn    = map_row_ig
    else:
        print("ERROR: Unknown platform '{}'. Use 'fb' or 'ig'.".format(platform))
        sys.exit(1)

    out_rows = []
    skipped  = 0
    for row in raw_rows:
        if is_summary_row(row):
            skipped += 1
            continue
        dt, out = map_fn(row, vis_cols)
        out_rows.append((dt, out))

    # Sort oldest-first (rows with no date go to the end)
    out_rows.sort(key=lambda x: x[0] if x[0] else datetime.datetime.max)
    sorted_rows = [r[1] for r in out_rows]

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=vis_cols)
        writer.writeheader()
        writer.writerows(sorted_rows)

    print("Output: {} ({} data rows written, {} skipped)".format(output_path, len(sorted_rows), skipped))
    print("Columns: {}".format(len(vis_cols)))
    return sorted_rows


def process_custom(
    raw_csv_path: str,
    visible_columns: list,
    column_map: dict,
    output_path: str,
    skip_summary: bool = True,
    encoding: str = "utf-8-sig",
    auto_match: bool = False,
):
    """Process with a fully custom column list and mapping (advanced usage)."""
    headers, raw_rows = read_csv(raw_csv_path, encoding)
    print("Input : {} ({} rows, {} columns)".format(raw_csv_path, len(raw_rows), len(headers)))

    if auto_match and not column_map:
        column_map = smart_match_columns(visible_columns, headers)
        print("Auto-matched {} columns.".format(len(column_map)))

    empty_cols = [c for c in visible_columns if c not in column_map]
    if empty_cols:
        print("No mapping for (will be empty): {}".format(", ".join(empty_cols)))

    id_col = headers[0] if headers else "Post ID"
    out_rows_with_dt = []
    skipped = 0

    for row in raw_rows:
        if skip_summary and is_summary_row(row, id_col):
            skipped += 1
            continue

        out = {c: "" for c in visible_columns}
        for gs_col, raw_col in column_map.items():
            if gs_col in out and raw_col in row:
                out[gs_col] = row[raw_col]

        if not out.get("Organic/Paid"):
            out["Organic/Paid"] = "Organic"

        # Datetime handling
        dt = None
        for pt_key in ("Publish Time", "Publish time", "publish time"):
            pt = out.get(pt_key, row.get(pt_key, "")).strip()
            if pt:
                dt = parse_datetime(pt)
                if dt:
                    out[pt_key]      = dt.strftime("%m/%d/%Y %H:%M")
                    out["Post Date"] = dt.strftime("%d/%m/%Y")
                    out["Year"]      = str(dt.year)
                    out["Quarter"]   = "Q{}".format((dt.month - 1) // 3 + 1)
                break

        out_rows_with_dt.append((dt, out))

    out_rows_with_dt.sort(key=lambda x: x[0] if x[0] else datetime.datetime.max)
    sorted_rows = [r[1] for r in out_rows_with_dt]

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=visible_columns)
        writer.writeheader()
        writer.writerows(sorted_rows)

    print("Output: {} ({} rows written, {} skipped)".format(output_path, len(sorted_rows), skipped))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_kv_string(s: str) -> dict:
    result = {}
    for pair in s.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def read_lines_from_file(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


def read_kv_from_file(path: str) -> dict:
    result = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Map raw social media CSVs to Google Sheet column structure"
    )
    parser.add_argument("--raw-csv",   required=True, help="Path to the raw CSV file")
    parser.add_argument("--output",    required=True, help="Output CSV path")
    parser.add_argument("--platform",  choices=["fb", "ig"],
                        help="Platform preset: 'fb' or 'ig' (uses built-in column rules)")
    parser.add_argument("--visible-columns",      help="Comma-separated GSheet visible column names")
    parser.add_argument("--visible-columns-file", help="File with visible columns (one per line)")
    parser.add_argument("--column-map",           help="SheetCol=RawCol mappings, comma-separated")
    parser.add_argument("--column-map-file",      help="File with SheetCol=RawCol mappings")
    parser.add_argument("--keep-summary",  action="store_true", help="Keep summary rows")
    parser.add_argument("--auto-match",    action="store_true", help="Auto-match columns using heuristics")
    parser.add_argument("--encoding",      default="utf-8-sig", help="Raw CSV encoding (default: utf-8-sig)")

    args = parser.parse_args()

    if args.platform:
        # ── Platform preset mode ──────────────────────────────────────────────
        process_platform(
            raw_csv_path=args.raw_csv,
            output_path=args.output,
            platform=args.platform,
            encoding=args.encoding,
        )
    else:
        # ── Custom mode ───────────────────────────────────────────────────────
        if args.visible_columns_file:
            visible_columns = read_lines_from_file(args.visible_columns_file)
        elif args.visible_columns:
            visible_columns = [c.strip() for c in args.visible_columns.split(",")]
        else:
            print("ERROR: Provide --platform, --visible-columns, or --visible-columns-file")
            sys.exit(1)

        if args.column_map_file:
            column_map = read_kv_from_file(args.column_map_file)
        elif args.column_map:
            column_map = parse_kv_string(args.column_map)
        else:
            column_map = {}

        process_custom(
            raw_csv_path=args.raw_csv,
            visible_columns=visible_columns,
            column_map=column_map,
            output_path=args.output,
            skip_summary=not args.keep_summary,
            encoding=args.encoding,
            auto_match=args.auto_match or not column_map,
        )


if __name__ == "__main__":
    main()
