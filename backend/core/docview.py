"""Turns a Word (.docx) file into a plain, safe HTML page so it can be viewed in the browser.

Only text, basic formatting, lists, tables and small pictures are shown. Scripts, macros, links and anything active are never
carried over, every piece of text is escaped, and the page is served sandboxed (see complaints.views._file_response)."""
import base64
import html
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_XML = 20 * 1024 * 1024
MAX_IMAGE = 2 * 1024 * 1024
MAX_IMAGES_TOTAL = 8 * 1024 * 1024
MAX_PARAGRAPHS = 20000
MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif"}
CSS = ("body{font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#222;margin:0;padding:24px 28px;max-width:860px}"
       "h1,h2,h3,h4,h5,h6{line-height:1.3;margin:1.1em 0 .4em}p{margin:.5em 0}table{border-collapse:collapse;margin:.8em 0;max-width:100%}"
       "td,th{border:1px solid #ccc;padding:5px 8px;vertical-align:top}img{max-width:100%;height:auto}ul{margin:.4em 0 .4em 1.2em}"
       ".note{color:#777;font-size:13px}")


class Unreadable(Exception):
    pass


class _State:
    def __init__(self, z):
        self.images_total = 0
        self.paragraphs = 0
        self.rels = {}
        try:
            for rel in _xml(z, "word/_rels/document.xml.rels").iter(REL + "Relationship"):
                self.rels[rel.get("Id")] = rel.get("Target", "")
        except Unreadable:
            pass
        self.z = z


def _xml(z, name):
    try:
        info = z.getinfo(name)
    except KeyError:
        raise Unreadable("missing " + name)
    if info.file_size > MAX_XML:
        raise Unreadable("part too large")
    data = z.read(name)
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:  # no entity tricks
        raise Unreadable("unsafe xml")
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise Unreadable("bad xml")


def _flag(rpr, tag):
    el = rpr.find(W + tag) if rpr is not None else None
    return el is not None and el.get(W + "val", "true") not in ("0", "false", "none")


def _image(st, run):
    out = []
    for blip in run.iter(A + "blip"):
        target = st.rels.get(blip.get(R + "embed"), "")
        ext = target.rsplit(".", 1)[-1].lower()
        if ext not in MIME or ".." in target or target.startswith("/"):
            continue
        try:
            data = st.z.read("word/" + target)
        except KeyError:
            continue
        if len(data) > MAX_IMAGE or st.images_total + len(data) > MAX_IMAGES_TOTAL:
            out.append('<span class="note">[picture not shown: too large]</span>')
            continue
        st.images_total += len(data)
        out.append(f'<img alt="" src="data:{MIME[ext]};base64,{base64.b64encode(data).decode()}">')
    return "".join(out)


def _runs(st, p):
    out = []
    for node in p.iter():
        if node.tag == W + "r":
            rpr = node.find(W + "rPr")
            text = []
            for child in node:
                if child.tag == W + "t":
                    text.append(html.escape(child.text or ""))
                elif child.tag == W + "tab":
                    text.append("&emsp;")
                elif child.tag in (W + "br", W + "cr"):
                    text.append("<br>")
                elif child.tag == W + "drawing":
                    text.append(_image(st, child))
            s = "".join(text)
            if not s:
                continue
            if _flag(rpr, "b"):
                s = f"<strong>{s}</strong>"
            if _flag(rpr, "i"):
                s = f"<em>{s}</em>"
            if _flag(rpr, "u"):
                s = f"<u>{s}</u>"
            if _flag(rpr, "strike"):
                s = f"<s>{s}</s>"
            out.append(s)
    return "".join(out)


def _paragraph(st, p):
    st.paragraphs += 1
    if st.paragraphs > MAX_PARAGRAPHS:
        raise Unreadable("too long")
    ppr = p.find(W + "pPr")
    style = ""
    align = ""
    listed = False
    if ppr is not None:
        ps = ppr.find(W + "pStyle")
        style = (ps.get(W + "val") if ps is not None else "") or ""
        jc = ppr.find(W + "jc")
        align = jc.get(W + "val") if jc is not None else ""
        listed = ppr.find(W + "numPr") is not None
    body = _runs(st, p)
    css = {"center": "text-align:center", "right": "text-align:right", "both": "text-align:justify"}.get(align, "")
    attr = f' style="{css}"' if css else ""
    low = style.lower()
    if low.startswith("heading") and low[7:].isdigit() and 1 <= int(low[7:]) <= 6:
        return "h", f"<h{int(low[7:])}{attr}>{body}</h{int(low[7:])}>"
    if low in ("title", "subtitle"):
        return "h", f"<h1{attr}>{body}</h1>"
    if listed or low.startswith("listparagraph"):
        return "li", f"<li>{body}</li>"
    return "p", f"<p{attr}>{body or '&nbsp;'}</p>"


def _table(st, tbl, depth=0):
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            cells.append("<td>" + _blocks(st, tc, depth + 1) + "</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def _blocks(st, parent, depth=0):
    if depth > 4:
        return ""
    out, in_list = [], False
    for el in parent:
        kind, markup = None, ""
        if el.tag == W + "p":
            kind, markup = _paragraph(st, el)
        elif el.tag == W + "tbl":
            kind, markup = "t", _table(st, el, depth)
        else:
            continue
        if kind == "li" and not in_list:
            out.append("<ul>"); in_list = True
        elif kind != "li" and in_list:
            out.append("</ul>"); in_list = False
        out.append(markup)
    if in_list:
        out.append("</ul>")
    return "".join(out)


def docx_to_html(fieldfile):
    """Returns a complete HTML page for the .docx, or raises Unreadable."""
    try:
        with fieldfile.open("rb") as fh, zipfile.ZipFile(fh) as z:
            if sum(i.file_size for i in z.infolist()) > 400 * 1024 * 1024:
                raise Unreadable("expands too much")
            st = _State(z)
            body = _xml(z, "word/document.xml").find(W + "body")
            if body is None:
                raise Unreadable("no body")
            content = _blocks(st, body)
    except zipfile.BadZipFile:
        raise Unreadable("not a zip")
    if not content.strip():
        content = '<p class="note">This document has no text to show.</p>'
    return f'<!doctype html><html><head><meta charset="utf-8"><title>Document preview</title><style>{CSS}</style></head><body>{content}</body></html>'
