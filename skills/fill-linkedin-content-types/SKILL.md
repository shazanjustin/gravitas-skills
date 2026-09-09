---
name: fill-linkedin-content-types
description: Inspect LinkedIn Page post exports and fill missing media/content-format labels without changing other data. Use when a user provides a LinkedIn raw-data file such as CSV, TSV, XLSX, XLSM, or legacy XLS and asks to identify, complete, repair, or validate a Content Type column using the linked posts as evidence.
---

# Fill LinkedIn Content Types

Complete missing LinkedIn post formats in a copy of the user's raw-data file. Do not require a paid API, LinkedIn login, or subscription.

## Workflow

1. Preserve the source file. Work on a copy or write to a new output path.
2. Run the bundled inspector:

```bash
python scripts/linkedin_content_types.py inspect "INPUT_FILE"
```

The command locates the data sheet and header row, detects common URL/caption/date columns, and creates a review JSON containing only rows whose `Content Type` is missing. It supports CSV, TSV, XLSX, and XLSM directly. For legacy XLS, it uses a local LibreOffice conversion when available.

3. Read [references/classification-guide.md](references/classification-guide.md).
4. Investigate every row in the review JSON:
   - Open its public LinkedIn post URL when available.
   - Use visible media behavior and export metadata as evidence.
   - Preserve every existing non-empty content type.
   - Do not infer a format from caption wording alone.
   - If a post is private, deleted, blocked, or genuinely ambiguous, leave `content_type` empty and set `needs_review` to `true`.
5. Fill each decision's `content_type`, `confidence`, and `evidence` in the review JSON.
6. Apply the reviewed decisions:

```bash
python scripts/linkedin_content_types.py apply "INPUT_FILE" \
  --decisions "INPUT_FILE_linkedin_content_type_review.json"
```

7. Validate the completed output:

```bash
python scripts/linkedin_content_types.py validate "OUTPUT_FILE"
```

8. Report:
   - output path;
   - number filled and still unresolved;
   - count by content type;
   - any inaccessible or ambiguous rows.

## Canonical labels

Use only:

- `Image`
- `Video`
- `Document`
- `Article`
- `Poll`
- `Event`
- `Text`

Treat multi-image galleries as `Image`; LinkedIn PDF/slide carousels as `Document`; and external URL previews, LinkedIn articles, or newsletters as `Article`.

## Data-safety rules

- Never overwrite the source unless the user explicitly requests it.
- Change only the detected `Content Type` cells. If the column does not exist, append it.
- Keep sheet names, row order, formulas, formatting, links, and all unrelated values unchanged.
- Never replace an existing type unless the user explicitly requests correction and `--overwrite` is used.
- Do not bypass LinkedIn access controls or request credentials. Ask for a screenshot or exported media-type evidence when a public post cannot be inspected.

## Portability

The helper uses the Python standard library only. No paid service is required. A chat-only AI without file execution cannot modify a workbook; in that case, provide the review JSON or a row/type mapping for the user to apply with the bundled script on any computer with Python 3.

For legacy `.xls`, install free LibreOffice or save the file as `.xlsx`/`.csv` first. The script never converts an `.xls` in place.
