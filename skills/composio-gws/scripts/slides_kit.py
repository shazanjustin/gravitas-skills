# -*- coding: utf-8 -*-
"""
Layout helpers for Google Slides decks that must not overlap.

Every rule here came from rendering thumbnails of a real 36-slide report build and
finding things broken. Use it with composio_gws.py (transport). deck_lib.py is still
fine for quick decks; reach for this when a deck has tables, stats and dense text.

The four ideas:

  1. Layers. Requests go out in this order: slides and table reshapes, backgrounds,
     images, then text, chips and table fills. Slides stacks later objects on top,
     so images created last cover the labels and chips drawn over them.
  2. Measured flow. Place each block below the estimated height of the block above
     it, never at a guessed constant. text_height() is deliberately conservative.
  3. Real, compact tables. A table created through the API gets cell padding the API
     cannot change, so rows render at roughly 0.33in minimum and push into whatever
     sits below. Duplicate a compact table that already exists in the deck (tables
     imported from PowerPoint have tight padding) and reshape it: rows and columns
     inserted into it keep that padding, and minRowHeight then holds exactly.
  4. One text box per value and label, so a label can never drift away from its
     number.

Coordinates are inches; the API wants EMU, and the helpers convert.
"""
import io, json, math, urllib.request

EMU = 914400
FONT = "Open Sans"
MIN_COL_W = 0.445          # the API rejects column widths under 32pt (406400 EMU)
INSET_Y = 0.05             # text box inset, top and bottom; not settable through the API


def I(x):
    return int(round(x * EMU))


def rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def u16(s):
    """Slides text indices count UTF-16 code units."""
    return len(s.encode("utf-16-le")) // 2


def style(size=None, color=None, weight=None, italic=None, link=None, underline=None, font=FONT):
    """(style, fields) for updateTextStyle.

    Weight 700 and above only renders when bold is also true; weight 600 with bold
    false renders correctly. So bold is derived from the weight, never passed.
    """
    s, f = {}, []
    if size is not None:
        s["fontSize"] = {"magnitude": size, "unit": "PT"}; f.append("fontSize")
    if weight is not None:
        s["fontFamily"] = font
        s["weightedFontFamily"] = {"fontFamily": font, "weight": weight}
        s["bold"] = weight >= 700
        f += ["fontFamily", "weightedFontFamily", "bold"]
    if color is not None:
        s["foregroundColor"] = {"opaqueColor": {"rgbColor": rgb(color)}}; f.append("foregroundColor")
    if italic is not None:
        s["italic"] = italic; f.append("italic")
    if link is not None:
        s["link"] = {"url": link}; f.append("link")
    if underline is not None:
        s["underline"] = underline; f.append("underline")
    return s, f


def text_height(runs, width_in, size_pt, spacing=100):
    """Conservative height in inches of wrapped text in a text box of this width.

    Open Sans lines are about 1.36x the font size, and average characters about
    0.5em wide. Horizontal insets (0.1in each side) and vertical insets are included.
    """
    full = runs if isinstance(runs, str) else "".join(t for t, _ in runs)
    per_line = max(8, (width_in - 0.2) / (size_pt * 0.5 / 72))
    lines = sum(max(1, math.ceil(len(p) / per_line)) for p in full.split("\n"))
    return lines * size_pt * 1.38 / 72 * spacing / 100 + 2 * INSET_Y


class Layers:
    """Collects Slides API requests in four layers and sends them in stacking order."""

    def __init__(self, prefix="k"):
        self.pre, self.bg, self.img, self.fg = [], [], [], []
        self.prefix, self._n = prefix, 0

    def nid(self, kind):
        self._n += 1
        return f"{self.prefix}{kind}{self._n:05d}"      # object ids must be 5+ chars

    def _q(self, layer):
        return {"pre": self.pre, "bg": self.bg, "fg": self.fg}[layer]

    @staticmethod
    def el(page, x, y, w, h):
        return {"pageObjectId": page,
                "size": {"width": {"magnitude": max(I(w), 12700), "unit": "EMU"}, "height": {"magnitude": max(I(h), 12700), "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": I(x), "translateY": I(y), "unit": "EMU"}}

    # ---- pages
    def blank_slide(self, sid, layout_id=None):
        ref = {"layoutId": layout_id} if layout_id else {"predefinedLayout": "BLANK"}
        self.pre.append({"createSlide": {"objectId": sid, "slideLayoutReference": ref}})
        return sid

    # ---- shapes
    def rect(self, page, x, y, w, h, fill, kind="RECTANGLE", outline=None, weight=0.75, dash="SOLID", layer="bg"):
        oid = self.nid("r"); q = self._q(layer)
        q.append({"createShape": {"objectId": oid, "shapeType": kind, "elementProperties": self.el(page, x, y, w, h)}})
        props = {"shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}} if fill else {"propertyState": "NOT_RENDERED"},
                 "outline": ({"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(outline)}}}, "weight": {"magnitude": weight, "unit": "PT"}, "dashStyle": dash}
                             if outline else {"propertyState": "NOT_RENDERED"})}
        q.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": props, "fields": "shapeBackgroundFill,outline"}})
        return oid

    def line(self, page, x1, y1, x2, y2, color="#211F1C", weight=1.0, dash="SOLID", layer="fg"):
        oid = self.nid("l"); q = self._q(layer)
        q.append({"createLine": {"objectId": oid, "lineCategory": "STRAIGHT", "elementProperties": self.el(page, min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))}})
        q.append({"updateLineProperties": {"objectId": oid, "lineProperties": {"lineFill": {"solidFill": {"color": {"rgbColor": rgb(color)}}},
                  "weight": {"magnitude": weight, "unit": "PT"}, "dashStyle": dash}, "fields": "lineFill,weight,dashStyle"}})
        return oid

    def image(self, page, url, x, y, w, h):
        """Image fits inside the box, keeping its aspect ratio. The URL must be publicly fetchable at insert time."""
        if url:
            self.img.append({"createImage": {"objectId": self.nid("i"), "url": url, "elementProperties": self.el(page, x, y, w, h)}})

    def text(self, page, x, y, w, h, runs, size=9, color="#211F1C", weight=400, align="START", valign="TOP", spacing=100, italic=False, layer="fg"):
        """runs: a str, or [(text, {size, color, weight, italic, link, underline}), ...]."""
        if isinstance(runs, str):
            runs = [(runs, {})]
        full = "".join(t for t, _ in runs)
        if not full.strip():
            return None
        oid = self.nid("t"); q = self._q(layer)
        q.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX", "elementProperties": self.el(page, x, y, w, h)}})
        q.append({"insertText": {"objectId": oid, "text": full, "insertionIndex": 0}})
        s, f = style(size, color, weight, italic)
        q.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "ALL"}, "style": s, "fields": ",".join(f)}})
        q.append({"updateParagraphStyle": {"objectId": oid, "textRange": {"type": "ALL"},
                  "style": {"alignment": align, "lineSpacing": spacing, "spaceAbove": {"magnitude": 0, "unit": "PT"}, "spaceBelow": {"magnitude": 0, "unit": "PT"}},
                  "fields": "alignment,lineSpacing,spaceAbove,spaceBelow"}})
        i = 0
        for t, o in runs:
            n = u16(t)
            if o and n:
                s, f = style(o.get("size"), o.get("color"), o.get("weight"), o.get("italic"), o.get("link"), o.get("underline"))
                if f:
                    q.append({"updateTextStyle": {"objectId": oid, "textRange": {"type": "FIXED_RANGE", "startIndex": i, "endIndex": i + n}, "style": s, "fields": ",".join(f)}})
            i += n
        # text boxes never autofit: overflow is silent, which is why flow() measures first
        q.append({"updateShapeProperties": {"objectId": oid, "shapeProperties": {"contentAlignment": valign, "autofit": {"autofitType": "NONE"}},
                  "fields": "contentAlignment,autofit.autofitType"}})
        return oid

    def flow(self, page, x, y, w, runs, size=8.5, gap=0.08, **kw):
        """Text box sized to its estimated height. Returns the next free y."""
        h = text_height(runs, w + 0.1, size, kw.get("spacing", 100))
        self.text(page, x - 0.1, y, w + 0.1, h, runs, size=size, **kw)
        return y + h + gap

    def stat_block(self, page, x, y, w, title, items, pitch=0.56, accent="#E60000", ink="#211F1C", label="#7C7470", hair="#E6E0DC"):
        """Section label, a rule, then a 2-column grid of (value, label) pairs. Returns the next free y.

        Each value and its label share one text box. Two separate boxes drifted apart:
        a 14pt value overflows a short box and gets pushed up onto the rule, leaving its
        label floating directly above the next value.
        """
        pitch = max(pitch, 0.5)
        self.text(page, x - 0.1, y, w + 0.1, 0.2, title.upper(), size=6.5, color=accent, weight=700, valign="BOTTOM")
        self.line(page, x, y + 0.24, x + w, y + 0.24, ink, 1.25)
        cw = (w - 0.2) / 2
        for k, (v, lab) in enumerate(items):
            cx = x + (k % 2) * (cw + 0.2); cy = y + 0.3 + (k // 2) * pitch
            self.text(page, cx - 0.1, cy, cw + 0.2, 0.47, [(str(v), {"size": 14, "weight": 800, "color": ink}), ("\n" + lab.upper(), {"size": 5.6, "weight": 700, "color": label})],
                      size=14, color=ink, weight=800)
            self.line(page, cx, cy + 0.48, cx + cw, cy + 0.48, hair, 0.5)
        return y + 0.3 + math.ceil(len(items) / 2) * pitch

    # ---- sending
    def send(self, c, pid, chunk=200, extra_after=()):
        """Send pre, bg, images (8 per call, retried one by one on failure), fg, then extra_after. Returns failed image URLs."""
        def batch(reqs, n):
            for i in range(0, len(reqs), n):
                c.execute("GOOGLESLIDES_PRESENTATIONS_BATCH_UPDATE", {"presentationId": pid, "requests": reqs[i:i + n]})
        batch(self.pre, 150)
        batch(self.bg, chunk)
        failed = []
        for i in range(0, len(self.img), 8):
            part = self.img[i:i + 8]
            try:
                batch(part, 8)
            except Exception:
                for rq in part:
                    try:
                        batch([rq], 1)
                    except Exception as e:
                        failed.append((rq["createImage"]["url"][:100], str(e)[:120]))
        batch(self.fg, chunk)
        for reqs in extra_after:
            batch(reqs, 100)
        return failed


def walk(elements):
    for e in elements:
        yield e
        if "elementGroup" in e:
            yield from walk(e["elementGroup"]["children"])


class CompactTables:
    """Real tables with exact row heights, made by duplicating a compact table the deck already has.

    Find a candidate with find_compact_table(deck). Each call to slide_with_table()
    duplicates the template's slide, deletes everything on the copy except the table,
    then reshapes rows, columns, widths, position and row heights. Keep the template
    slide in the deck until the build is final, and delete it once at the end.
    """

    def __init__(self, layers, deck, table_id):
        self.L = layers
        self.slide = next(s for s in deck["slides"] if any(e["objectId"] == table_id for e in walk(s.get("pageElements", []))))
        t = next(e for e in walk(self.slide["pageElements"]) if e["objectId"] == table_id)["table"]
        self.table_id, self.rows, self.cols = table_id, t["rows"], t["columns"]
        self.has_text = {(i, j) for i, r in enumerate(t["tableRows"]) for j, cl in enumerate(r["tableCells"])
                         if "".join(te.get("textRun", {}).get("content", "") for te in cl.get("text", {}).get("textElements", [])).strip()}

    def slide_with_table(self, sid, nrows, widths, x, y, row_h, header_h=None, total_h=None):
        ids = {self.slide["objectId"]: sid}
        for k, e in enumerate(walk(self.slide["pageElements"])):
            ids[e["objectId"]] = f"{sid}_x{k:02d}"
        L = self.L
        L.pre.append({"duplicateObject": {"objectId": self.slide["objectId"], "objectIds": ids}})
        for e in self.slide["pageElements"]:
            if e["objectId"] != self.table_id:
                L.pre.append({"deleteObject": {"objectId": ids[e["objectId"]]}})
        tb, nc = ids[self.table_id], len(widths)
        for ri in range(self.rows - 1, nrows - 1, -1):
            L.pre.append({"deleteTableRow": {"tableObjectId": tb, "cellLocation": {"rowIndex": ri, "columnIndex": 0}}})
        if nrows > self.rows:
            L.pre.append({"insertTableRows": {"tableObjectId": tb, "cellLocation": {"rowIndex": self.rows - 1, "columnIndex": 0}, "insertBelow": True, "number": nrows - self.rows}})
        if nc > self.cols:
            L.pre.append({"insertTableColumns": {"tableObjectId": tb, "cellLocation": {"rowIndex": 0, "columnIndex": self.cols - 1}, "insertRight": True, "number": nc - self.cols}})
        for cj in range(self.cols - 1, nc - 1, -1):
            L.pre.append({"deleteTableColumn": {"tableObjectId": tb, "cellLocation": {"rowIndex": 0, "columnIndex": cj}}})
        for j, w in enumerate(widths):
            if w < MIN_COL_W:
                raise ValueError(f"column {j} is {w}in; the API minimum is 32pt ({MIN_COL_W}in)")
            L.pre.append({"updateTableColumnProperties": {"objectId": tb, "columnIndices": [j], "tableColumnProperties": {"columnWidth": {"magnitude": I(w), "unit": "EMU"}}, "fields": "columnWidth"}})
        L.pre.append({"updatePageElementTransform": {"objectId": tb, "applyMode": "ABSOLUTE", "transform": {"scaleX": 1, "scaleY": 1, "translateX": I(x), "translateY": I(y), "unit": "EMU"}}})
        for idx, hgt in ((list(range(nrows)), row_h), ([0], header_h or row_h), ([nrows - 1], total_h or row_h)):
            L.pre.append({"updateTableRowProperties": {"objectId": tb, "rowIndices": idx, "tableRowProperties": {"minRowHeight": {"magnitude": I(hgt), "unit": "EMU"}}, "fields": "minRowHeight"}})
        return {"id": tb, "nrows": nrows, "ncols": nc, "height": row_h * nrows - row_h * 2 + (header_h or row_h) + (total_h or row_h)}

    def fill(self, handle, rows, aligns, size=7.5, header_fill="#E60000", band="#F7F5F3", total_fill="#EFEAE7", segment_fill="#FBE4E2",
             body_color="#46403C", ink="#211F1C", segment_color="#9A0100", indent_pt=4):
        """rows: [(kind, cells)] with kind header, body, total or segment (a full-width label row).

        A cell is a str or a runs list [(text, style)]. Runs can carry a link, so a
        'Link' column can hold a clickable arrow.
        """
        L, tb, nc = self.L, handle["id"], handle["ncols"]
        for i, (kind, cells) in enumerate(rows):
            for j in range(nc):
                if (i, j) in self.has_text and j < self.cols and i < self.rows:
                    L.fg.append({"deleteText": {"objectId": tb, "cellLocation": {"rowIndex": i, "columnIndex": j}, "textRange": {"type": "ALL"}}})
            fill = {"header": header_fill, "total": total_fill, "segment": segment_fill}.get(kind) or (band if i % 2 == 0 else "#FFFFFF")
            L.fg.append({"updateTableCellProperties": {"objectId": tb, "tableRange": {"location": {"rowIndex": i, "columnIndex": 0}, "rowSpan": 1, "columnSpan": nc},
                         "tableCellProperties": {"tableCellBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}}, "contentAlignment": "MIDDLE"},
                         "fields": "tableCellBackgroundFill.solidFill.color,contentAlignment"}})
            if kind == "segment":
                L.fg.append({"mergeTableCells": {"objectId": tb, "tableRange": {"location": {"rowIndex": i, "columnIndex": 0}, "rowSpan": 1, "columnSpan": nc}}})
                cells = [cells[0]]
            base = {"header": (size - 0.7, "#FFFFFF", 700), "total": (size, ink, 800), "segment": (size - 0.3, segment_color, 700)}.get(kind, (size, body_color, 400))
            for j, cell in enumerate(cells):
                runs = [(cell, {})] if isinstance(cell, str) else cell
                full = "".join(t for t, _ in runs)
                if not full.strip():
                    continue
                loc = {"rowIndex": i, "columnIndex": j}
                L.fg.append({"insertText": {"objectId": tb, "cellLocation": loc, "text": full, "insertionIndex": 0}})
                s, f = style(*base)
                L.fg.append({"updateTextStyle": {"objectId": tb, "cellLocation": loc, "textRange": {"type": "ALL"}, "style": s, "fields": ",".join(f)}})
                L.fg.append({"updateParagraphStyle": {"objectId": tb, "cellLocation": loc, "textRange": {"type": "ALL"},
                             "style": {"alignment": "START" if kind == "segment" else aligns[j], "lineSpacing": 100,
                                       "spaceAbove": {"magnitude": 0, "unit": "PT"}, "spaceBelow": {"magnitude": 0, "unit": "PT"},
                                       "indentStart": {"magnitude": indent_pt, "unit": "PT"}, "indentFirstLine": {"magnitude": indent_pt, "unit": "PT"},
                                       "indentEnd": {"magnitude": indent_pt, "unit": "PT"}},
                             "fields": "alignment,lineSpacing,spaceAbove,spaceBelow,indentStart,indentFirstLine,indentEnd"}})
                k = 0
                for t, o in runs:
                    n = u16(t)
                    if o and n and kind != "header":
                        s, f = style(o.get("size"), o.get("color"), o.get("weight"), o.get("italic"), o.get("link"), o.get("underline"))
                        if f:
                            L.fg.append({"updateTextStyle": {"objectId": tb, "cellLocation": loc, "textRange": {"type": "FIXED_RANGE", "startIndex": k, "endIndex": k + n}, "style": s, "fields": ",".join(f)}})
                    k += n


def find_compact_table(deck, max_row_h_in=0.14):
    """The existing table with the smallest row height, if any row is at most max_row_h_in. Returns its object id or None."""
    best = None
    for s in deck.get("slides", []):
        for e in walk(s.get("pageElements", [])):
            if "table" not in e:
                continue
            hs = [r.get("rowHeight", {}).get("magnitude", 10 ** 9) / EMU for r in e["table"]["tableRows"]]
            if hs and min(hs) <= max_row_h_in and (best is None or min(hs) < best[0]):
                best = (min(hs), e["objectId"])
    return best[1] if best else None


def contact_sheet(c, pid, slide_ids, path, per_row=2, width=960):
    """Render slide thumbnails into one image so a whole deck can be checked at a glance. Needs Pillow."""
    from PIL import Image, ImageDraw
    order = [s["objectId"] for s in c.deck_get(pid)["slides"]]
    res = c.parallel([("GOOGLESLIDES_PRESENTATIONS_PAGES_GET_THUMBNAIL", {"presentationId": pid, "pageObjectId": sid, "thumbnailProperties": {"thumbnailSize": "LARGE"}})
                      for sid in slide_ids])
    ims = []
    for sid, r in zip(slide_ids, res):
        url = r.get("contentUrl") or r.get("response_data", {}).get("contentUrl")
        im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=60).read())).convert("RGB")
        ims.append((order.index(sid) + 1 if sid in order else "?", im.resize((width, round(im.height * width / im.width)))))
    h = ims[0][1].height; rows = math.ceil(len(ims) / per_row)
    out = Image.new("RGB", (per_row * (width + 12) + 12, rows * (h + 32) + 8), "#444444"); d = ImageDraw.Draw(out)
    for k, (n, im) in enumerate(ims):
        x = 12 + (k % per_row) * (width + 12); y = 8 + (k // per_row) * (h + 32)
        d.text((x, y + 6), f"slide {n}", fill="white"); out.paste(im, (x, y + 26))
    out.save(path)
    return path
