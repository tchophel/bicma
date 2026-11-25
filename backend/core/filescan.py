"""Safety check for every uploaded file (complaint forms, staff uploads, replies, additional information).

Built-in checks need no extra software:
  * the file's real content must match its extension (a program renamed to .png is refused);
  * programs and scripts hidden in any file are refused (Windows/Linux/Mac executables, shell scripts);
  * images are fully decoded (broken or booby-trapped images fail) and may not carry embedded scripts;
  * PDFs that run JavaScript, launch programs or embed files are refused;
  * Word / Excel / PowerPoint files with macros, ActiveX or embedded programs are refused, and zip "bombs" too;
  * the standard antivirus test file (EICAR) is refused.
If a ClamAV server is configured (CLAMAV_HOST), the file is also scanned with it. These checks are strong but not a
replacement for a full antivirus: enabling ClamAV is recommended in production.
"""
import io
import logging
import re
import socket
import struct
import zipfile

from django.conf import settings

log = logging.getLogger(__name__)

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
EXECUTABLE_HEADS = (b"MZ", b"\x7fELF", b"\xfe\xed\xfa", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"#!", b"\xcf\xfa\xed")
OOXML = {"docx", "xlsx", "pptx"}
OLE_EXT = {"doc", "xls", "ppt"}
BAD_ZIP_PARTS = ("vbaproject.bin", "/macros/", "/activex/", "/embeddings/")
BAD_ZIP_ENDS = (".exe", ".dll", ".js", ".vbs", ".bat", ".cmd", ".ps1", ".scr", ".jar", ".com", ".msi")
PDF_DANGER = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/SubmitForm", b"/ImportData")
SCRIPT_MARKS = (b"<script", b"<?php", b"<%", b"javascript:", b"<iframe", b"onerror=")
MAX_ZIP_RATIO, MAX_ZIP_BYTES, MAX_ZIP_ENTRIES = 100, 300 * 1024 * 1024, 5000


class Unsafe(Exception):
    """Raised with a short, user-readable reason."""


def _read(f):
    f.seek(0)
    data = f.read()
    f.seek(0)
    return data


def _check_type(ext, data):
    head = data[:16]
    if ext == "pdf" and not data.lstrip()[:5] == b"%PDF-":
        raise Unsafe("it is not a real PDF")
    if ext in ("jpg", "jpeg") and not head.startswith(b"\xff\xd8\xff"):
        raise Unsafe("it is not a real JPEG image")
    if ext == "png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Unsafe("it is not a real PNG image")
    if ext in OOXML and not head.startswith(b"PK\x03\x04"):
        raise Unsafe("it is not a real Office document")
    if ext in OLE_EXT and not head.startswith(OLE):
        raise Unsafe("it is not a real Office document")
    if ext == "mp3" and not (head.startswith(b"ID3") or (head[0:1] == b"\xff" and head[1:2] and head[1] & 0xE0 == 0xE0)):
        raise Unsafe("it is not a real MP3 audio file")
    if ext == "mp4" and data[4:8] not in (b"ftyp", b"moov", b"mdat", b"free", b"wide"):
        raise Unsafe("it is not a real MP4 video file")
    if ext in ("txt", "csv"):
        sample = data[:65536]
        if b"\x00" in sample or sum(1 for b in sample if b < 9 or 13 < b < 32) > max(8, len(sample) // 50):
            raise Unsafe("it is not a plain text file")


def _check_image(ext, data):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse "decompression bombs"
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
    except Exception:
        raise Unsafe("the image is damaged or not a valid picture")
    low = data.lower()
    if any(m in low for m in SCRIPT_MARKS):
        raise Unsafe("the image contains hidden script code")


def _check_pdf(data):
    for mark in PDF_DANGER:
        if re.search(re.escape(mark) + rb"(?![A-Za-z])", data):
            raise Unsafe("the PDF contains active content (scripts or programs)")


def _check_ooxml(data):
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except zipfile.BadZipFile:
        raise Unsafe("the document is damaged")
    if len(infos) > MAX_ZIP_ENTRIES:
        raise Unsafe("the document has too many parts")
    total = sum(i.file_size for i in infos)
    packed = max(1, sum(i.compress_size for i in infos))
    if total > MAX_ZIP_BYTES or total / packed > MAX_ZIP_RATIO:
        raise Unsafe("the document expands to an unsafe size")
    for i in infos:
        name = "/" + i.filename.lower()
        if any(p in name for p in BAD_ZIP_PARTS) or name.endswith(BAD_ZIP_ENDS):
            raise Unsafe("the document contains macros or embedded programs")


def _check_ole(data):
    low = data.lower()
    if b"_vba_project" in low or b"vba" in low and b"macros" in low or b"auto_open" in low or b"autoopen" in low or b"shell(" in low:
        raise Unsafe("the document contains macros")


def _clamav(data):
    host = getattr(settings, "CLAMAV_HOST", "")
    if not host:
        return
    try:
        with socket.create_connection((host, int(getattr(settings, "CLAMAV_PORT", 3310))), timeout=10) as s:
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]
                s.sendall(struct.pack("!I", len(chunk)) + chunk)
            s.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0") and len(reply) < 4096:
                part = s.recv(1024)
                if not part:
                    break
                reply += part
    except OSError:
        log.exception("ClamAV is not reachable")
        if getattr(settings, "CLAMAV_REQUIRED", False):
            raise Unsafe("the file could not be checked for viruses right now. Please try again later")
        return
    text = reply.rstrip(b"\0").decode("utf-8", "replace")
    if "FOUND" in text:
        raise Unsafe("a virus was found in it")
    if not text.endswith(": OK"):
        raise OSError("Antivirus did not return a valid scan result")
    return True


def scan(f, ext):
    """Raise Unsafe(reason) if the uploaded file looks harmful. `ext` is the lower-case extension."""
    data = _read(f)
    if EICAR in data:
        raise Unsafe("a virus was found in it")
    if data[:4] in EXECUTABLE_HEADS or any(data.startswith(h) for h in EXECUTABLE_HEADS):
        raise Unsafe("it is a program, not a document")
    _check_type(ext, data)
    if ext in ("jpg", "jpeg", "png"):
        _check_image(ext, data)
    elif ext == "pdf":
        _check_pdf(data)
    elif ext in OOXML:
        _check_ooxml(data)
    elif ext in OLE_EXT:
        _check_ole(data)
    return bool(_clamav(data))
