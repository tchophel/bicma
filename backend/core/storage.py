"""Settings > Storage: how much space the system uses, what takes the most, and a PDF of it for the Administrator."""
import os
import shutil

from django.conf import settings
from django.db import connection
from django.utils import timezone

FOLDER_LABELS = {"attachments": "Complaint documents", "followups": "Follow-up documents", "profile_photos": "Staff profile photos"}


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _folders():
    root = str(settings.MEDIA_ROOT)
    out = []
    if not os.path.isdir(root):
        return out
    for entry in sorted(os.scandir(root), key=lambda e: e.name):
        size = files = 0
        if entry.is_dir(follow_symlinks=False):
            for base, _dirs, names in os.walk(entry.path):
                for name in names:
                    try:
                        size += os.path.getsize(os.path.join(base, name))
                        files += 1
                    except OSError:
                        pass
        elif entry.is_file(follow_symlinks=False):
            size, files = entry.stat().st_size, 1
        out.append({"name": FOLDER_LABELS.get(entry.name, entry.name), "folder": entry.name, "bytes": size, "files": files})
    return sorted(out, key=lambda f: -f["bytes"])


def _tables(limit=10):
    with connection.cursor() as cur:
        cur.execute("select pg_database_size(current_database())")
        total = cur.fetchone()[0]
        cur.execute("select relname, pg_total_relation_size(relid), n_live_tup from pg_stat_user_tables order by 2 desc limit %s", [limit])
        rows = [{"table": r[0], "bytes": int(r[1]), "rows": int(r[2])} for r in cur.fetchall()]
    return total, rows


def overview():
    from complaints.models import Attachment
    from django.db.models import Count, Sum
    disk = shutil.disk_usage(str(settings.MEDIA_ROOT) if os.path.isdir(str(settings.MEDIA_ROOT)) else "/")
    db_bytes, tables = _tables()
    folders = _folders()
    files_bytes = sum(f["bytes"] for f in folders)
    biggest = [{"id": str(a.pk), "name": a.original_name, "bytes": a.size, "type": a.content_type, "visibility": a.visibility,
                "reference": a.complaint.reference, "added": a.created_at.isoformat()}
               for a in Attachment.objects.select_related("complaint").order_by("-size")[:15]]
    kinds = [{"type": k["content_type"] or "unknown", "bytes": k["total"] or 0, "files": k["n"]}
             for k in Attachment.objects.values("content_type").annotate(total=Sum("size"), n=Count("id")).order_by("-total")[:8]]
    used_pct = round(disk.used * 100 / disk.total) if disk.total else 0
    tips = []
    if used_pct >= 85:
        tips.append(f"The disk is {used_pct}% full. Add disk space or free some soon, before uploads and the database fail.")
    elif used_pct >= 70:
        tips.append(f"The disk is {used_pct}% full. Plan to add space.")
    if biggest and biggest[0]["bytes"] >= 10 * 1024 * 1024:
        tips.append(f"The biggest document is {human(biggest[0]['bytes'])} ({biggest[0]['name']}, {biggest[0]['reference']}). Ask for a smaller or compressed copy of very large scans and videos.")
    if files_bytes > db_bytes * 2:
        tips.append("Most of the space is uploaded documents. Move old closed-case documents to cheaper storage or archive them, keeping the record in the system.")
    elif tables and tables[0]["bytes"] > db_bytes * 0.4:
        tips.append(f"The database table '{tables[0]['table']}' is the largest. Old log rows in it can be archived or trimmed.")
    tips.append("Complaint records and their documents are kept for the legal period and cannot be deleted from the system. Archive or expand storage instead.")
    from complaints import compress
    return {"checked_at": timezone.now().isoformat(),
            "compress": {"enabled": compress.enabled(), "waiting": compress.waiting(), "saved": compress.saved()},
            "disk": {"total": disk.total, "used": disk.used, "free": disk.free, "used_pct": used_pct},
            "database": {"bytes": db_bytes, "tables": tables},
            "files": {"bytes": files_bytes, "count": sum(f["files"] for f in folders), "folders": folders, "kinds": kinds, "biggest": biggest},
            "tips": tips}


def report_pdf(by=""):
    import html
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    o = overview()
    e = lambda v: html.escape(str(v or ""))
    st = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=st["BodyText"], fontSize=8, leading=10)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Storage report", leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    def table(head, rows, widths):
        t = Table([[Paragraph(f"<b>{h}</b>", small) for h in head]] + [[Paragraph(e(c), small) for c in r] for r in rows], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t
    d = o["disk"]
    flow = [Paragraph("BICMA CMS: storage report", st["Title"]),
            Paragraph(f"Made {timezone.localtime():%Y-%m-%d %H:%M}" + (f" for {e(by)}" if by else ""), st["Normal"]), Spacer(1, 10),
            Paragraph("Summary", st["Heading2"]),
            table(["Item", "Size"], [["Disk total", human(d["total"])], ["Disk used", f"{human(d['used'])} ({d['used_pct']}%)"], ["Disk free", human(d["free"])],
                                     ["Database", human(o["database"]["bytes"])], ["Uploaded documents", f"{human(o['files']['bytes'])} in {o['files']['count']} files"]], [200, 340]),
            Spacer(1, 10), Paragraph("What to do", st["Heading2"])]
    flow += [Paragraph("- " + e(t), small) for t in o["tips"]]
    flow += [Spacer(1, 10), Paragraph("Uploaded documents by folder", st["Heading2"]),
             table(["Folder", "Files", "Size"], [[f["name"], f["files"], human(f["bytes"])] for f in o["files"]["folders"]], [300, 80, 160]),
             Spacer(1, 10), Paragraph("Pictures of resolved complaints", st["Heading2"]),
             Paragraph(f"Shrinking is {'on' if o['compress']['enabled'] else 'off'}. Saved so far: {human(o['compress']['saved']['bytes'])} in {o['compress']['saved']['files']} pictures. "
                       f"Waiting: {o['compress']['waiting']['files']} pictures ({human(o['compress']['waiting']['bytes'])}).", small),
             Spacer(1, 10), Paragraph("Uploaded documents by type", st["Heading2"]),
             table(["Type", "Files", "Size"], [[k["type"], k["files"], human(k["bytes"])] for k in o["files"]["kinds"]], [300, 80, 160]),
             Spacer(1, 10), Paragraph("Largest documents", st["Heading2"]),
             table(["Document", "Complaint", "Size", "Added"], [[b["name"], b["reference"], human(b["bytes"]), b["added"][:10]] for b in o["files"]["biggest"]], [220, 130, 80, 110]),
             Spacer(1, 10), Paragraph("Largest database tables", st["Heading2"]),
             table(["Table", "Rows", "Size"], [[t["table"], t["rows"], human(t["bytes"])] for t in o["database"]["tables"]], [300, 80, 160])]
    doc.build(flow)
    return buf.getvalue()
