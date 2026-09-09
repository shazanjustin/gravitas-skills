#!/usr/bin/env python3
"""Inspect and fill LinkedIn Content Type values without paid dependencies."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"x": MAIN_NS, "r": DOC_REL_NS, "p": PKG_REL_NS}
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", DOC_REL_NS)

TARGET_NAMES = {"contenttype", "contentformat", "mediatype", "postformat"}
URL_NAMES = {"postlink", "posturl", "permalink", "linkedinposturl", "url", "link"}
CAPTION_NAMES = {
    "posttitle", "posttext", "postcaption", "description", "caption",
    "commentary", "postcopy", "postname",
}
DATE_NAMES = {"createddate", "createdtime", "postdate", "publishtime", "date"}
MISSING_VALUES = {"", "na", "n/a", "#n/a", "null", "none", "unknown", "-", "--"}
CANONICAL = {"Image", "Video", "Document", "Article", "Poll", "Event", "Text"}
TYPE_ALIASES = {
    "image": "Image", "photo": "Image", "gallery": "Image",
    "multiimage": "Image", "multipleimages": "Image",
    "video": "Video", "nativevideo": "Video",
    "document": "Document", "pdf": "Document", "carousel": "Document",
    "documentcarousel": "Document", "slides": "Document",
    "article": "Article", "link": "Article", "externallink": "Article",
    "newsletter": "Article",
    "poll": "Poll", "event": "Event",
    "text": "Text", "textonly": "Text",
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def is_missing(value: object) -> bool:
    return str(value or "").strip().lower() in MISSING_VALUES


def column_number(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - 64
    return number


def column_letters(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def decode_text_file(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path.name}")


def detect_delimiter(text: str, path: Path) -> str:
    fallback = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    try:
        return csv.Sniffer().sniff(text[:16384], delimiters=",\t;|").delimiter
    except csv.Error:
        return fallback


def read_delimited(path: Path) -> tuple[list[list[str]], str, str]:
    text, encoding = decode_text_file(path)
    delimiter = detect_delimiter(text, path)
    return list(csv.reader(io.StringIO(text), delimiter=delimiter)), delimiter, encoding


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.findall(".//x:t", NS))
            for item in root.findall("x:si", NS)]


def workbook_sheets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("p:Relationship", NS)
    }
    result = []
    for sheet in workbook.findall("x:sheets/x:sheet", NS):
        target = targets[sheet.attrib[f"{{{DOC_REL_NS}}}id"]]
        if target.startswith("/"):
            sheet_path = target.lstrip("/")
        else:
            sheet_path = posixpath.normpath(str(PurePosixPath("xl") / target))
        result.append((sheet.attrib["name"], sheet_path))
    return result


def cell_value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t", "")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", NS))
    value = cell.find("x:v", NS)
    if value is None or value.text is None:
        return ""
    if kind == "s":
        try:
            return strings[int(value.text)]
        except (IndexError, ValueError):
            return ""
    if kind == "b":
        return "TRUE" if value.text == "1" else "FALSE"
    return value.text


def parse_sheet(archive: zipfile.ZipFile, sheet_path: str) -> tuple[ET.Element, dict[int, dict[int, str]]]:
    root = ET.fromstring(archive.read(sheet_path))
    strings = shared_strings(archive)
    rows: dict[int, dict[int, str]] = {}
    for row in root.findall("x:sheetData/x:row", NS):
        row_number = int(row.attrib.get("r", "0"))
        values = {}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            if ref:
                values[column_number(ref)] = cell_value(cell, strings)
        rows[row_number] = values
    return root, rows


def detect_header(rows: dict[int, dict[int, str]]) -> tuple[int, dict[str, int | None]]:
    best: tuple[int, int, dict[str, int | None]] | None = None
    for row_number in sorted(rows)[:50]:
        values = rows[row_number]
        normalized = {norm(value): column for column, value in values.items() if str(value).strip()}
        target = next((normalized[name] for name in TARGET_NAMES if name in normalized), None)
        url = next((normalized[name] for name in URL_NAMES if name in normalized), None)
        caption = next((normalized[name] for name in CAPTION_NAMES if name in normalized), None)
        date = next((normalized[name] for name in DATE_NAMES if name in normalized), None)
        score = (8 if target else 0) + (6 if url else 0) + (3 if caption else 0) + (2 if date else 0)
        if (url or caption) and (best is None or score > best[0]):
            best = (score, row_number, {
                "target": target, "url": url, "caption": caption, "date": date,
            })
    if best is None:
        raise ValueError("Could not detect a LinkedIn post header row.")
    return best[1], best[2]


def choose_xlsx_sheet(path: Path, requested: str | None = None):
    with zipfile.ZipFile(path) as archive:
        candidates = []
        for name, sheet_path in workbook_sheets(archive):
            if requested and name != requested:
                continue
            root, rows = parse_sheet(archive, sheet_path)
            try:
                header_row, columns = detect_header(rows)
            except ValueError:
                continue
            score = (8 if columns["target"] else 0) + (6 if columns["url"] else 0)
            candidates.append((score, name, sheet_path, root, rows, header_row, columns))
    if not candidates:
        label = f" named {requested!r}" if requested else ""
        raise ValueError(f"Could not find a LinkedIn post sheet{label}.")
    return max(candidates, key=lambda item: item[0])


def collect_review_rows(
    rows: dict[int, dict[int, str]],
    header_row: int,
    columns: dict[str, int | None],
    include_existing: bool = False,
) -> list[dict[str, object]]:
    review = []
    for row_number in sorted(number for number in rows if number > header_row):
        values = rows[row_number]
        url = values.get(columns["url"], "") if columns["url"] else ""
        caption = values.get(columns["caption"], "") if columns["caption"] else ""
        date = values.get(columns["date"], "") if columns["date"] else ""
        existing = values.get(columns["target"], "") if columns["target"] else ""
        if not any(str(value).strip() for value in (url, caption, date)):
            continue
        if not include_existing and not is_missing(existing):
            continue
        review.append({
            "row_number": row_number,
            "url": url,
            "caption": caption,
            "date": date,
            "existing_content_type": existing,
            "content_type": "",
            "confidence": "",
            "evidence": "",
            "needs_review": False,
        })
    return review


def find_libreoffice() -> str | None:
    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return found
    for candidate in (
        Path(os.environ.get("ProgramFiles", "")) / "LibreOffice/program/soffice.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "LibreOffice/program/soffice.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def convert_xls(path: Path, output_dir: Path) -> Path:
    executable = find_libreoffice()
    if not executable:
        raise RuntimeError(
            "Legacy .xls requires free LibreOffice. Install it or save the file as .xlsx/.csv."
        )
    command = [
        executable, "--headless", "--convert-to", "xlsx",
        "--outdir", str(output_dir), str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    converted = output_dir / f"{path.stem}.xlsx"
    if result.returncode != 0 or not converted.exists():
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr or result.stdout}")
    return converted


def inspect_file(path: Path, sheet: str | None, include_existing: bool) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".txt"}:
        table, delimiter, encoding = read_delimited(path)
        rows = {
            number: {index + 1: value for index, value in enumerate(row)}
            for number, row in enumerate(table, 1)
        }
        header_row, columns = detect_header(rows)
        return {
            "input_file": str(path.resolve()),
            "file_type": suffix.lstrip("."),
            "sheet": None,
            "header_row": header_row,
            "detected_columns": columns,
            "delimiter": delimiter,
            "encoding": encoding,
            "rows": collect_review_rows(rows, header_row, columns, include_existing),
        }
    if suffix in {".xlsx", ".xlsm"}:
        _, name, _, _, rows, header_row, columns = choose_xlsx_sheet(path, sheet)
        return {
            "input_file": str(path.resolve()),
            "file_type": suffix.lstrip("."),
            "sheet": name,
            "header_row": header_row,
            "detected_columns": columns,
            "rows": collect_review_rows(rows, header_row, columns, include_existing),
        }
    if suffix == ".xls":
        with tempfile.TemporaryDirectory() as temp:
            converted = convert_xls(path, Path(temp))
            result = inspect_file(converted, sheet, include_existing)
        result["input_file"] = str(path.resolve())
        result["file_type"] = "xls"
        result["conversion_note"] = "Legacy XLS is converted to XLSX for safe editing."
        return result
    raise ValueError(f"Unsupported file type: {suffix or '(none)'}")


def canonical_type(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    canonical = TYPE_ALIASES.get(norm(raw), raw)
    if canonical not in CANONICAL:
        raise ValueError(f"Unsupported content type {raw!r}. Use: {', '.join(sorted(CANONICAL))}")
    return canonical


def load_decisions(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    decisions = payload.get("rows", payload.get("decisions", [])) if isinstance(payload, dict) else payload
    if not isinstance(decisions, list):
        raise ValueError("Decisions JSON must contain a rows or decisions list.")
    result = []
    for item in decisions:
        if not isinstance(item, dict) or "row_number" not in item:
            raise ValueError("Each decision needs row_number and content_type fields.")
        content_type = canonical_type(item.get("content_type"))
        if content_type:
            result.append({"row_number": int(item["row_number"]), "content_type": content_type})
    return result


def default_output(path: Path) -> Path:
    suffix = ".xlsx" if path.suffix.lower() == ".xls" else path.suffix
    return path.with_name(f"{path.stem}_content_types_completed{suffix}")


def set_inline_string(cell: ET.Element, value: str) -> None:
    for child in list(cell):
        cell.remove(child)
    cell.attrib["t"] = "inlineStr"
    inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
    text = ET.SubElement(inline, f"{{{MAIN_NS}}}t")
    if value != value.strip():
        text.attrib[f"{{{XML_NS}}}space"] = "preserve"
    text.text = value


def find_or_create_row(sheet_data: ET.Element, row_number: int) -> ET.Element:
    for row in sheet_data.findall("x:row", NS):
        current = int(row.attrib["r"])
        if current == row_number:
            return row
        if current > row_number:
            created = ET.Element(f"{{{MAIN_NS}}}row", {"r": str(row_number)})
            sheet_data.insert(list(sheet_data).index(row), created)
            return created
    return ET.SubElement(sheet_data, f"{{{MAIN_NS}}}row", {"r": str(row_number)})


def find_or_create_cell(row: ET.Element, row_number: int, column: int) -> ET.Element:
    ref = f"{column_letters(column)}{row_number}"
    for cell in row.findall("x:c", NS):
        current = column_number(cell.attrib["r"])
        if current == column:
            return cell
        if current > column:
            created = ET.Element(f"{{{MAIN_NS}}}c", {"r": ref})
            row.insert(list(row).index(cell), created)
            return created
    return ET.SubElement(row, f"{{{MAIN_NS}}}c", {"r": ref})


def copy_adjacent_style(row: ET.Element, cell: ET.Element, column: int) -> None:
    previous = next(
        (item for item in row.findall("x:c", NS)
         if column_number(item.attrib["r"]) == column - 1),
        None,
    )
    if previous is not None and "s" in previous.attrib:
        cell.attrib["s"] = previous.attrib["s"]


def extend_dimension(root: ET.Element, column: int, row_number: int) -> None:
    dimension = root.find("x:dimension", NS)
    if dimension is None:
        return
    ref = dimension.attrib.get("ref", "A1")
    start = ref.split(":", 1)[0]
    dimension.attrib["ref"] = f"{start}:{column_letters(column)}{row_number}"


def apply_xlsx(
    input_path: Path,
    output_path: Path,
    decisions: list[dict[str, object]],
    sheet_name: str | None,
    overwrite: bool,
) -> tuple[int, str]:
    _, name, sheet_path, root, rows, header_row, columns = choose_xlsx_sheet(input_path, sheet_name)
    target = columns["target"]
    appending_column = target is None
    if appending_column:
        target = max(rows.get(header_row, {0: ""})) + 1
    valid_rows = set(rows)
    sheet_data = root.find("x:sheetData", NS)
    if sheet_data is None:
        raise ValueError("Worksheet has no sheetData element.")
    header = find_or_create_row(sheet_data, header_row)
    header_cell = find_or_create_cell(header, header_row, target)
    if appending_column:
        copy_adjacent_style(header, header_cell, target)
    set_inline_string(header_cell, "Content Type")
    changed = 0
    for decision in decisions:
        row_number = int(decision["row_number"])
        if row_number not in valid_rows or row_number <= header_row:
            raise ValueError(f"Decision row {row_number} is not a data row in sheet {name!r}.")
        existing = rows[row_number].get(target, "")
        if not overwrite and not is_missing(existing):
            continue
        row = find_or_create_row(sheet_data, row_number)
        target_cell = find_or_create_cell(row, row_number, target)
        if appending_column:
            copy_adjacent_style(row, target_cell, target)
        set_inline_string(target_cell, str(decision["content_type"]))
        changed += 1
    if appending_column:
        extend_dimension(root, target, max(valid_rows))
    replacement = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.name}.tmp")
    with zipfile.ZipFile(input_path) as source, zipfile.ZipFile(temp_path, "w") as output:
        for info in source.infolist():
            output.writestr(info, replacement if info.filename == sheet_path else source.read(info.filename))
    temp_path.replace(output_path)
    return changed, name


def apply_delimited(
    input_path: Path,
    output_path: Path,
    decisions: list[dict[str, object]],
    overwrite: bool,
) -> tuple[int, None]:
    table, delimiter, _ = read_delimited(input_path)
    rows = {
        number: {index + 1: value for index, value in enumerate(row)}
        for number, row in enumerate(table, 1)
    }
    header_row, columns = detect_header(rows)
    target = columns["target"]
    if target is None:
        target = len(table[header_row - 1]) + 1
        table[header_row - 1].append("Content Type")
    changed = 0
    for decision in decisions:
        row_number = int(decision["row_number"])
        if row_number <= header_row or row_number > len(table):
            raise ValueError(f"Decision row {row_number} is not a data row.")
        row = table[row_number - 1]
        while len(row) < target:
            row.append("")
        if not overwrite and not is_missing(row[target - 1]):
            continue
        row[target - 1] = str(decision["content_type"])
        changed += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle, delimiter=delimiter, lineterminator="\n").writerows(table)
    return changed, None


def apply_file(
    input_path: Path,
    output_path: Path,
    decisions: list[dict[str, object]],
    sheet: str | None,
    overwrite: bool,
) -> tuple[int, str | None]:
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return apply_xlsx(input_path, output_path, decisions, sheet, overwrite)
    if suffix in {".csv", ".tsv", ".txt"}:
        return apply_delimited(input_path, output_path, decisions, overwrite)
    if suffix == ".xls":
        with tempfile.TemporaryDirectory() as temp:
            converted = convert_xls(input_path, Path(temp))
            return apply_xlsx(converted, output_path.with_suffix(".xlsx"), decisions, sheet, overwrite)
    raise ValueError(f"Unsupported file type: {suffix or '(none)'}")


def type_counts(path: Path, sheet: str | None) -> tuple[dict[str, int], int]:
    review_all = inspect_file(path, sheet, include_existing=True)
    counts: dict[str, int] = {}
    unresolved = 0
    for row in review_all["rows"]:
        existing = str(row["existing_content_type"] or "").strip()
        if is_missing(existing):
            unresolved += 1
        else:
            counts[existing] = counts.get(existing, 0) + 1
    return counts, unresolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Create a review JSON for missing types")
    inspect_parser.add_argument("input")
    inspect_parser.add_argument("--output")
    inspect_parser.add_argument("--sheet")
    inspect_parser.add_argument("--include-existing", action="store_true")
    apply_parser = subparsers.add_parser("apply", help="Apply reviewed JSON decisions")
    apply_parser.add_argument("input")
    apply_parser.add_argument("--decisions", required=True)
    apply_parser.add_argument("--output")
    apply_parser.add_argument("--sheet")
    apply_parser.add_argument("--overwrite", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="Count formats and unresolved rows")
    validate_parser.add_argument("input")
    validate_parser.add_argument("--sheet")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if args.command == "inspect":
        payload = inspect_file(input_path, args.sheet, args.include_existing)
        output = Path(args.output).expanduser().resolve() if args.output else input_path.with_name(
            f"{input_path.stem}_linkedin_content_type_review.json"
        )
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"review_file": str(output), "rows_to_review": len(payload["rows"])}, indent=2))
        return 0
    if args.command == "apply":
        decisions = load_decisions(Path(args.decisions).expanduser().resolve())
        output = Path(args.output).expanduser().resolve() if args.output else default_output(input_path)
        changed, sheet = apply_file(input_path, output, decisions, args.sheet, args.overwrite)
        actual_output = output.with_suffix(".xlsx") if input_path.suffix.lower() == ".xls" else output
        counts, unresolved = type_counts(actual_output, sheet)
        print(json.dumps({
            "output_file": str(actual_output),
            "rows_filled": changed,
            "unresolved_rows": unresolved,
            "content_type_counts": counts,
        }, indent=2))
        return 0
    counts, unresolved = type_counts(input_path, args.sheet)
    print(json.dumps({
        "input_file": str(input_path),
        "unresolved_rows": unresolved,
        "content_type_counts": counts,
    }, indent=2))
    return 1 if unresolved else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
