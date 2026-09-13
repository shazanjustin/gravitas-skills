---
name: composio-gws
description: >
  Fast Google Sheets, Slides and Drive access via Composio. Use whenever reading or
  writing a Google Sheet, building or updating a Google Slides deck, or finding
  files in Drive. Keep-alive REST client, roughly 40% faster than the MCP
  transport, plus a Slides layout library that builds a deck in a few batch calls.
---

# Composio: fast Google Workspace access

Three scripts. `composio_gws.py` is the transport, `deck_lib.py` builds quick
Slides decks, and `slides_kit.py` keeps dense decks (tables, stats, lots of text)
from overlapping.

## Setup

`COMPOSIO_API_KEY` and `COMPOSIO_EXTERNAL_USER_ID` resolve in this order:

1. explicit arguments to `Composio()`
2. the environment
3. the Gravitas Gateway, `GET /secret/COMPOSIO_API_KEY`
4. a local `.env` file, path overridable with `COMPOSIO_ENV_FILE`

> **The gateway does not hold these yet.** As of 2026-09-10 it serves
> `METRICOOL_TOKEN`, `APIFY_API_KEY` and the `SOCIAL_ATLAS_*` set, and no
> Composio credentials. Until someone adds them with `wrangler secret put`,
> step 3 finds nothing, and anyone without the author's local `.env` has to set
> the two variables in their own environment. Step 3 is already wired, so the
> skill starts working the moment those secrets land.

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "scripts"))
import composio_gws as C
c = C.Composio()
```

## The four things that make it fast

1. **REST execute, not MCP.** Composio's `/api/v3/tools/execute/{TOOL}` returns
   plain JSON. The MCP endpoint wraps everything in JSON-RPC + SSE and measured
   ~1.98s median vs ~1.23s for REST on the same call.
2. **Keep-alive.** One `http.client.HTTPSConnection` per thread, reused. Saves a
   TLS handshake on every call after the first.
3. **Batch first.** `deck_batch()` sends up to 100 Slides API requests per HTTP
   call. A 6-slide deck is 655 requests, which goes out in 7 calls in ~11s.
   One-at-a-time would be ~14 minutes.
4. **`c.parallel([(tool, args), ...])`** for independent calls (thumbnails,
   multi-sheet reads). Ordered results, 6 workers by default.

## Hard-won gotchas

- **Never shell out to curl for these payloads.** Spreadsheet formulas and
  object ids are full of `$` and `%`. Build requests in Python and POST them.
- **Two MCP servers exist.** `ev-discord` (`8ee020f3-...`) has sheets/drive/
  notion/nocodb but **no googleslides**. `ev-discord-with-slides`
  (`033fa126-...`) has all five. `.env.collected` points at the one WITHOUT
  slides, which is why Slides looks unavailable when it is actually connected.
  The REST path used here sidesteps the MCP server entirely and always works.
- **Custom fonts need `weightedFontFamily`.** Setting only `fontFamily` on shape
  text is silently normalised back to Arial by Slides. Send both:
  `{"fontFamily": F, "weightedFontFamily": {"fontFamily": F, "weight": 700 if bold else 400}}`
  and list both in `fields`. Table cells keep a bare `fontFamily`, so a deck can
  end up with Inter tables and Arial everything else. `deck_lib` now does this.
- **Watch `sys.path` shadowing.** If a build script does
  `sys.path.insert(0, <skill scripts>)` and a copy of `deck_lib.py` also sits in
  the working directory, the SKILL copy wins. Editing the local copy then does
  nothing. Keep one canonical copy here and import it.
- **Delete by explicit file id, never by a name query.**
  `GOOGLEDRIVE_GOOGLE_DRIVE_DELETE_FOLDER_OR_FILE_ACTION` deletes
  **permanently** (it does not go to trash, so there is no undo). Only ever pass
  ids you captured from files you created in this session. A `name contains`
  sweep will match the user's files too.
- **Slides object ids must be 5+ characters.** `s001` is rejected; use `shp001`.
- **Font weight 700+ only renders when `bold` is true.** Weight 700 or 800 with
  `bold: false` renders regular; weight 600 with `bold: false` is fine. Derive
  `bold = weight >= 700`.
- **`GOOGLESLIDES_PRESENTATIONS_CREATE` has no page size**, so API-made decks are
  10 x 5.625in. For another size, copy an existing native deck of that size and
  clear its slides. Its `duplicatePresentationId` field is rejected by Google.
- **`GOOGLESLIDES_PRESENTATIONS_GET` returns HTTP 413** on large image-heavy decks.
- **Shared-drive files:** `GOOGLEDRIVE_COPY_FILE` answers 404 "File not found"
  even though Slides can read the deck, because it cannot pass
  `supportsAllDrives`. Use `c.drive_copy()`, which goes through Composio's proxy.
- **There is NO `GOOGLESHEETS_VALUES_UPDATE` on this project.** Verified against
  the live tool list (`GET /api/v3/tools?toolkit_slug=googlesheets`) on
  2026-09-02: the only writer is **`GOOGLESHEETS_BATCH_UPDATE`**, which takes
  `spreadsheet_id` + `sheet_name` + `first_cell_location` + `values`, *not* an A1
  range. `sheet_write()` now splits the range and calls it. Rows of differing
  length are rejected, so it pads ragged rows, and it chunks at 50 rows.
- **`GOOGLESHEETS_FORMAT_CELL`** does background colour, bold, italic, size.
  There is **no font colour**. Pace calls ~1.3s apart or Sheets 429s. It requires
  a **numeric `worksheet_id`** and **0-based half-open** `start/end_row_index`,
  `start/end_column_index` — a sheet name plus an A1 range fails with the
  unhelpful *"Invalid request data provided - following fields are missing"*.
  `sheet_format()` now converts for you; pass `_ids=c.sheet_ids(ssid)` when
  formatting many ranges so it does not refetch metadata each call.
- **`GOOGLESHEETS_GET_SPREADSHEET_INFO` nests its whole payload under
  `response_data`.** `sheet_info()` unwraps it; `.get("sheets")` on the raw
  result silently returns nothing.
- **Writing past a tab's grid fails**, it does not auto-grow: *"Range exceeds
  grid limits. Max rows: N"*. Size the tab at creation
  (`sheet_add_tab(..., rows=, cols=)`) with room for anything you plan to append.
- **Ads/Sheets bulk reads:** chunk long date ranges. Google returns
  `code 1 / subcode 99 "unknown error"` on oversized requests rather than a
  useful message.

## Sheets

```python
c.sheet_names(ssid)                        # -> ['Tab1', ...]
c.sheet_ids(ssid)                          # -> {'Tab1': 352911252}  (FORMAT_CELL needs this)
c.sheet_read(ssid, ["MODEL!A1:L73"])       # -> [[row, ...]]
c.sheet_add_tab(ssid, "MODEL", index=0, rows=400, cols=12)
c.sheet_write(ssid, "MODEL!A1", grid)      # USER_ENTERED; pads ragged rows, chunks at 50
c.sheet_format(ssid, "MODEL", "A1:L1", bold=True, rgb=(0.87, 0.87, 0.87))

# formatting many rows: resolve the tab ids once
ids = c.sheet_ids(ssid)
for r in header_rows:
    c.sheet_format(ssid, "MODEL", "A%d:L%d" % (r, r), bold=True, _ids=ids)
    time.sleep(1.35)
```

## Slides

```python
from deck_lib import Deck, IN, W, H, ORANGE, INK, GREY, WHITE, LINE

d = Deck()
s = d.slide("sIntro")                       # BLANK layout
d.shape(s, 0, 0, W, H, fill=INK)
d.text(s, IN, IN, 6*IN, 400000, "Title", size=32, bold=True, color=WHITE)
d.line(s, x1, y1, x2, y2)                   # arrows default on
tid = d.table(s, x, y, width, rows, cols)
d.col_widths(tid, [...])                    # EMU, must sum to `width`
d.cell(tid, 0, 0, "Header", bold=True, fill=ORANGE, color=WHITE)

pid = c.deck_create("My Deck")
c.deck_batch(pid, d.req)                    # everything, in ~7 HTTP calls
```

Coordinates are **EMU**: `IN = 914400`. A 16:9 slide is `W, H = 10*IN, 5.625*IN`.

**To rebuild in place** (keeps the URL stable, which matters once a link is
shared) wipe the slides first rather than creating a new presentation:

```python
old = [s["objectId"] for s in c.deck_get(pid).get("slides", [])]
c.deck_batch(pid, [{"deleteObject": {"objectId": o}} for o in old])
```

**Always render thumbnails and actually look at them before declaring a deck
done.** Text boxes do not autofit, so overflow is silent:

```python
jobs = [("GOOGLESLIDES_PRESENTATIONS_PAGES_GET_THUMBNAIL",
         {"presentationId": pid, "pageObjectId": sid,
          "thumbnailProperties": {"thumbnailSize": "LARGE"}}) for sid in ids]
for sid, r in zip(ids, c.parallel(jobs)):
    urllib.request.urlretrieve(r["contentUrl"], "slide_%s.png" % sid)
```

## Slides that do not overlap

Verified 2026-09-13 by rendering every slide of a 36-slide report. The first
build looked finished and was not: tables ran into text, labels sat on rules,
images hid chips. Each rule below fixed a real defect. `slides_kit.py` encodes them.

1. **Never trust a table created through the API for layout.** Its cell padding
   cannot be changed, so rows render about 0.33in tall however small the text,
   and the table pushes into whatever is placed below it. Instead, duplicate a
   compact table the deck already has (`find_compact_table()`; tables imported
   from PowerPoint are tight), then reshape it. Rows and columns inserted into it
   keep the tight padding, so `minRowHeight` holds exactly and a table's height is
   rows x row height. Duplicate the template's whole slide (`duplicateObject`),
   delete everything else on the copy, and delete the template slide once at the
   end, not on every run.
2. **Column widths under 32pt (0.444in) are rejected.** Two narrow tables side by
   side usually break this; use one full-width table per slide and put context in
   a side column.
3. **Never fake a table with columns of text boxes.** It looks aligned until one
   cell wraps, and it cannot be edited as a table.
4. **Send in layers:** slides and table reshapes, backgrounds, images, then text,
   chips and table fills. Later objects stack on top, so images sent last cover
   the chips and labels on them.
5. **Measure, then place.** Put each block below the estimated height of the one
   above (`text_height()`, `Layers.flow()`), not at a guessed constant. Text
   boxes do not autofit and have a fixed 0.05in inset top and bottom that
   positions must allow for.
6. **Keep a value and its label in one text box** (`Layers.stat_block()`). In
   two boxes, a 14pt value overflows upward onto its rule and the label floats
   above the next value, so the reader pairs the wrong label and number.
7. **Short labels in narrow columns.** "Contest: 4 contents" in a 0.55in Date
   column wraps to four lines and makes the whole row tall. Put "Total" there
   and the count in the wide column.
8. **Pin template slides by object id, never by text search.** Searching for a
   slide title also matches the agenda slide that lists it.
9. **Look at every slide.** `contact_sheet()` renders them into one image. Check
   for overlap, clipped text and stray elements before calling a deck done.

```python
from composio_gws import Composio
from slides_kit import Layers, CompactTables, find_compact_table, contact_sheet

c = Composio(); deck = c.deck_get(pid)
L = Layers(prefix="rpt")
tables = CompactTables(L, deck, find_compact_table(deck))

t = tables.slide_with_table("rpt_s01", nrows=6, widths=[1.6, 1.0, 1.4, 1.4],
                            x=0.45, y=1.4, row_h=0.26, header_h=0.24, total_h=0.24)
tables.fill(t, [("header", ["Platform", "Posts", "Reach", "ER"]),
                ("body", ["Instagram", "40", "120,000", "1.20%"]),
                ("total", ["All", "60", "150,000", "1.00%"])],
            aligns=["START", "END", "END", "END"])
y = 1.4 + t["height"] + 0.2                 # the next block starts below the real table
y = L.stat_block("rpt_s01", 0.45, y, 4.9, "Delivered", [("150,000", "Reach"), ("1.00%", "ER")])
failed_images = L.send(c, pid)
contact_sheet(c, pid, ["rpt_s01"], "check.png")
```

**Rebuild in place** (a shared link stays valid): delete slides you created
(give them a common id prefix), keep template slides until the final run, and
if the deck would become empty mid-build, create a temporary slide first.

## Drive

```python
c.drive_find("Tiger Brokers")               # name contains, not trashed
c.drive_move(file_id, folder_id)
c.drive_copy(file_id, "New title")         # works on shared drives, lands next to the source
c.drive_trash(file_id)                      # recoverable, unlike the permanent delete tool
```

New presentations land in My Drive root; move them if a folder is wanted.
