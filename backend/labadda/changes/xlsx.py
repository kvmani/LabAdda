"""Read the first sheet of an .xlsx workbook with the standard library; nothing touches disk.

Every cell comes back as text, so an employee number such as 00123 keeps its zeros. The workbook is
untrusted input: sizes, entry counts and XML features are limited before anything is parsed.
"""

import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from ..errors import Invalid

MAX_ENTRIES = 200
MAX_UNCOMPRESSED = 20 * 1024 * 1024
MAX_PART = 12 * 1024 * 1024
MAX_COLUMNS = 40
MAX_SHEET_ROWS = 5000
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK\x03\x04"
SHEET_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
PACKAGE_KIND = "application/vnd.openxmlformats-package.relationships+xml"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
MAIN = f"{{{SHEET_MAIN}}}"
REL = f"{{{RELATIONS}}}"
PACKAGE_REL = f"{{{PACKAGE}}}"
CELL_REF = re.compile(r"^([A-Z]{1,3})([0-9]+)$")


def _bad(code: str, message: str) -> Invalid:
    return Invalid(code, message)


def looks_like_xlsx(data: bytes) -> bool:
    return data[:4] == ZIP_MAGIC or data[:8] == OLE_MAGIC


def _open(data: bytes) -> zipfile.ZipFile:
    if data[:8] == OLE_MAGIC:
        raise _bad(
            "import_encrypted",
            "That workbook is password-protected or in the old .xls format. Open it in Excel, remove the "
            "password, choose Save As, Excel Workbook (.xlsx), and try again.",
        )
    try:
        book = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad("import_not_xlsx", "That file is not a valid Excel workbook (.xlsx).") from None
    infos = book.infolist()
    if len(infos) > MAX_ENTRIES:
        raise _bad("import_unsafe", "That workbook has too many parts to be a staff list.")
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED or any(i.file_size > MAX_PART for i in infos):
        raise _bad("import_unsafe", "That workbook is far larger once opened than a staff list should be.")
    names = {info.filename.lower() for info in infos}
    if any("vbaproject" in name for name in names):
        raise _bad(
            "import_macros",
            "That workbook contains macros. Save a copy as a plain Excel Workbook (.xlsx) without macros.",
        )
    if "xl/workbook.xml" not in names:
        raise _bad("import_not_xlsx", "That file is not a valid Excel workbook (.xlsx).")
    return book


def _part(book: zipfile.ZipFile, name: str) -> bytes | None:
    """Read one part up to the cap, however the archive header describes its size."""
    try:
        with book.open(name) as handle:
            content = handle.read(MAX_PART + 1)
    except KeyError:
        return None
    if len(content) > MAX_PART:
        raise _bad("import_unsafe", "That workbook is far larger once opened than a staff list should be.")
    return content


def _xml(content: bytes) -> ET.Element:
    # Entity declarations are how XML expansion attacks work; a spreadsheet never needs them.
    if b"<!DOCTYPE" in content or b"<!ENTITY" in content:
        raise _bad("import_unsafe", "That workbook contains content that cannot be read safely.")
    try:
        return ET.fromstring(content)  # noqa: S314 - doctype and entities are refused above
    except ET.ParseError:
        raise _bad("import_not_xlsx", "That file is not a valid Excel workbook (.xlsx).") from None


def _text(element: ET.Element | None) -> str:
    """Joined text of an inline or shared string, leaving out phonetic guides."""
    if element is None:
        return ""
    parts = []
    for child in element:
        if child.tag == f"{MAIN}t":
            parts.append(child.text or "")
        elif child.tag == f"{MAIN}r":
            parts.append("".join(t.text or "" for t in child.findall(f"{MAIN}t")))
    return "".join(parts)


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    content = _part(book, "xl/sharedStrings.xml")
    if content is None:
        return []
    return [_text(item) for item in _xml(content).findall(f"{MAIN}si")]


def _first_sheet_path(book: zipfile.ZipFile) -> str:
    workbook = _xml(_part(book, "xl/workbook.xml") or b"")
    sheet = workbook.find(f"{MAIN}sheets/{MAIN}sheet")
    if sheet is None:
        raise _bad("import_empty", "The workbook has no sheets.")
    rid = sheet.get(f"{REL}id")
    rels = _part(book, "xl/_rels/workbook.xml.rels")
    if rid and rels:
        for rel in _xml(rels).findall(f"{PACKAGE_REL}Relationship"):
            if rel.get("Id") == rid:
                target = (rel.get("Target") or "").lstrip("/")
                return target if target.startswith("xl/") else f"xl/{target}"
    return "xl/worksheets/sheet1.xml"


def _column(reference: str) -> int:
    match = CELL_REF.match(reference)
    if not match:
        raise _bad("import_not_xlsx", "That file is not a valid Excel workbook (.xlsx).")
    number = 0
    for letter in match.group(1):
        number = number * 26 + ord(letter) - 64
    return number - 1


def _value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.get("t", "n")
    if kind == "inlineStr":
        return _text(cell.find(f"{MAIN}is"))
    raw = cell.find(f"{MAIN}v")
    text = raw.text if raw is not None and raw.text is not None else ""
    if kind == "s":
        try:
            return strings[int(text)]
        except (ValueError, IndexError):
            raise _bad("import_not_xlsx", "That file is not a valid Excel workbook (.xlsx).") from None
    if kind == "b":
        return "TRUE" if text == "1" else "FALSE"
    if kind == "e":
        return ""
    return text


def read_rows(data: bytes) -> list[list[str]]:
    """Rows of the first sheet as text; empty trailing rows and cells are kept as blank strings."""
    book = _open(data)
    strings = _shared_strings(book)
    sheet = _part(book, _first_sheet_path(book))
    if sheet is None:
        raise _bad("import_empty", "The workbook has no sheets.")
    rows: list[list[str]] = []
    for row in _xml(sheet).iter(f"{MAIN}row"):
        cells: dict[int, str] = {}
        for position, cell in enumerate(row.findall(f"{MAIN}c")):
            reference = cell.get("r")
            index = _column(reference) if reference else position
            if index >= MAX_COLUMNS:
                continue
            cells[index] = _value(cell, strings)
        if len(rows) >= MAX_SHEET_ROWS and not any(cells.values()):
            continue
        width = max(cells, default=-1) + 1
        rows.append([cells.get(index, "") for index in range(width)])
        if len(rows) > MAX_SHEET_ROWS * 2:
            raise _bad("import_too_large", "That sheet has too many rows to be a staff list.")
    return rows


def _letters(index: int) -> str:
    return chr(65 + index)


def write_rows(rows: list[list[str]]) -> bytes:
    """A minimal workbook of text cells, so values such as 00123 are not turned into numbers."""
    body = []
    for number, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_letters(i)}{number}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            for i, value in enumerate(row)
        )
        body.append(f'<row r="{number}">{cells}</row>')
    head = '<?xml version="1.0" encoding="UTF-8"?>'
    kind = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    link = f'<Relationship Id="rId1" Type="{RELATIONS}'
    parts = {
        "[Content_Types].xml": (
            f'{head}<Types xmlns="{CONTENT_TYPES}">'
            f'<Default Extension="rels" ContentType="{PACKAGE_KIND}"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{kind}.sheet.main+xml"/>'
            f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="{kind}.worksheet+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'{head}<Relationships xmlns="{PACKAGE}">'
            f'{link}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'{head}<workbook xmlns="{SHEET_MAIN}" xmlns:r="{RELATIONS}">'
            '<sheets><sheet name="Staff" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{head}<Relationships xmlns="{PACKAGE}">'
            f'{link}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'{head}<worksheet xmlns="{SHEET_MAIN}"><sheetData>' + "".join(body) + "</sheetData></worksheet>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as book:
        for name, content in parts.items():
            book.writestr(name, content)
    return buffer.getvalue()
