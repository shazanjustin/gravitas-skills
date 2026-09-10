# -*- coding: utf-8 -*-
"""Thin layer over the Google Slides API request format. EMU everywhere."""

IN = 914400
W, H = 10 * IN, int(5.625 * IN)

# ---- Tiger Brokers palette ----
ORANGE = (0xFF, 0x6A, 0x00)
ORANGE_D = (0xD9, 0x54, 0x00)
ORANGE_L = (0xFF, 0xF1, 0xE6)
INK = (0x16, 0x18, 0x1D)
INK_2 = (0x2A, 0x2E, 0x37)
GREY = (0x6B, 0x72, 0x80)
GREY_L = (0xF4, 0xF5, 0xF7)
LINE = (0xD8, 0xDC, 0xE3)
WHITE = (0xFF, 0xFF, 0xFF)
RED = (0xC0, 0x39, 0x2B)

FONT = "Arial"


def rgb(c):
    return {"red": c[0] / 255.0, "green": c[1] / 255.0, "blue": c[2] / 255.0}


def _el(page, x, y, w, h):
    return {"pageObjectId": page,
            "size": {"width": {"magnitude": w, "unit": "EMU"},
                     "height": {"magnitude": h, "unit": "EMU"}},
            "transform": {"scaleX": 1, "scaleY": 1, "translateX": x,
                          "translateY": y, "unit": "EMU"}}


class Deck:
    def __init__(self, prefix=""):
        # `prefix` keeps object ids unique when adding to a deck that already
        # holds elements from an earlier build. Slides rejects duplicate ids.
        self.req = []
        self.n = 0
        self.prefix = prefix

    def uid(self, p="obj"):
        self.n += 1
        return "%s%s%03d" % (p, self.prefix, self.n)

    def slide(self, sid):
        self.req.append({"createSlide": {
            "objectId": sid,
            "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        return sid

    def shape(self, page, x, y, w, h, fill=None, outline=None, kind="RECTANGLE",
              weight=1.25):
        oid = self.uid("shp")
        self.req.append({"createShape": {"objectId": oid, "shapeType": kind,
                                         "elementProperties": _el(page, x, y, w, h)}})
        props, fields = {}, []
        if fill is not None:
            props["shapeBackgroundFill"] = {"solidFill": {"color": {"rgbColor": rgb(fill)}}}
            fields.append("shapeBackgroundFill.solidFill.color")
        else:
            props["shapeBackgroundFill"] = {"solidFill": {"alpha": 0,
                                                          "color": {"rgbColor": rgb(WHITE)}}}
            fields.append("shapeBackgroundFill.solidFill.alpha")
        if outline is not None:
            props["outline"] = {"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(outline)}}},
                                "weight": {"magnitude": int(weight * 12700), "unit": "EMU"},
                                "dashStyle": "SOLID"}
            fields.append("outline")
        else:
            props["outline"] = {"propertyState": "NOT_RENDERED"}
            fields.append("outline.propertyState")
        self.req.append({"updateShapeProperties": {
            "objectId": oid, "fields": ",".join(fields), "shapeProperties": props}})
        return oid

    def text(self, page, x, y, w, h, content, size=12, color=INK, bold=False,
             align="START", valign=None, spacing=100, font=None):
        oid = self.uid("txt")
        self.req.append({"createShape": {"objectId": oid, "shapeType": "TEXT_BOX",
                                         "elementProperties": _el(page, x, y, w, h)}})
        self.req.append({"insertText": {"objectId": oid, "text": content,
                                        "insertionIndex": 0}})
        self.req.append({"updateTextStyle": {
            "objectId": oid, "textRange": {"type": "ALL"},
            "style": {"fontSize": {"magnitude": size, "unit": "PT"},
                      "bold": bold, "fontFamily": font or FONT,
                      "weightedFontFamily": {"fontFamily": font or FONT,
                                             "weight": 700 if bold else 400},
                      "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
            "fields": "fontSize,bold,fontFamily,weightedFontFamily,foregroundColor"}})
        self.req.append({"updateParagraphStyle": {
            "objectId": oid, "textRange": {"type": "ALL"},
            "style": {"alignment": align,
                      "lineSpacing": spacing,
                      "spaceBelow": {"magnitude": 2, "unit": "PT"}},
            "fields": "alignment,lineSpacing,spaceBelow"}})
        if valign:
            self.req.append({"updateShapeProperties": {
                "objectId": oid, "fields": "contentAlignment",
                "shapeProperties": {"contentAlignment": valign}}})
        self.req.append({"updateShapeProperties": {
            "objectId": oid, "fields": "autofit.autofitType",
            "shapeProperties": {"autofit": {"autofitType": "NONE"}}}})
        return oid

    def line(self, page, x1, y1, x2, y2, color=LINE, weight=1.0, arrow=True):
        oid = self.uid("lin")
        w, h = max(abs(x2 - x1), 1), max(abs(y2 - y1), 1)
        self.req.append({"createLine": {
            "objectId": oid, "lineCategory": "STRAIGHT",
            "elementProperties": _el(page, min(x1, x2), min(y1, y2), w, h)}})
        upd = {"lineFill": {"solidFill": {"color": {"rgbColor": rgb(color)}}},
               "weight": {"magnitude": int(weight * 12700), "unit": "EMU"}}
        f = "lineFill.solidFill.color,weight"
        if arrow:
            upd["endArrow"] = "FILL_ARROW"
            f += ",endArrow"
        self.req.append({"updateLineProperties": {
            "objectId": oid, "fields": f, "lineProperties": upd}})
        return oid

    def table(self, page, x, y, w, rows, cols):
        oid = self.uid("tbl")
        self.req.append({"createTable": {
            "objectId": oid, "rows": rows, "columns": cols,
            "elementProperties": {"pageObjectId": page,
                                  "size": {"width": {"magnitude": w, "unit": "EMU"},
                                           "height": {"magnitude": 100, "unit": "EMU"}},
                                  "transform": {"scaleX": 1, "scaleY": 1,
                                                "translateX": x, "translateY": y,
                                                "unit": "EMU"}}}})
        return oid

    def cell(self, tid, r, c, txt, size=8, color=INK, bold=False, fill=None,
             align="START"):
        if txt:
            self.req.append({"insertText": {"objectId": tid,
                                            "cellLocation": {"rowIndex": r, "columnIndex": c},
                                            "text": txt, "insertionIndex": 0}})
            self.req.append({"updateTextStyle": {
                "objectId": tid, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "textRange": {"type": "ALL"},
                "style": {"fontSize": {"magnitude": size, "unit": "PT"}, "bold": bold,
                          "fontFamily": FONT,
                          "weightedFontFamily": {"fontFamily": FONT,
                                                 "weight": 700 if bold else 400},
                          "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                "fields": "fontSize,bold,fontFamily,weightedFontFamily,foregroundColor"}})
            self.req.append({"updateParagraphStyle": {
                "objectId": tid, "cellLocation": {"rowIndex": r, "columnIndex": c},
                "textRange": {"type": "ALL"},
                "style": {"alignment": align}, "fields": "alignment"}})
        if fill is not None:
            self.req.append({"updateTableCellProperties": {
                "objectId": tid,
                "tableRange": {"location": {"rowIndex": r, "columnIndex": c},
                               "rowSpan": 1, "columnSpan": 1},
                "fields": "tableCellBackgroundFill.solidFill.color",
                "tableCellProperties": {"tableCellBackgroundFill": {
                    "solidFill": {"color": {"rgbColor": rgb(fill)}}}}}})

    def col_widths(self, tid, widths):
        for i, w in enumerate(widths):
            self.req.append({"updateTableColumnProperties": {
                "objectId": tid, "columnIndices": [i],
                "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "EMU"}},
                "fields": "columnWidth"}})
