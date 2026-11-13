"""Reading Excel and CSV staff sheets: headers, text cells, defaults, and hostile files."""

import io
import zipfile

import pytest

from labadda.changes import importer, staff_sheet, xlsx
from labadda.errors import ApiError

DOMAIN = "domain.in"
HEADER = [
    "full_name",
    "division",
    "section",
    "Emp No",
    "email",
    "Extension",
    "Group",
    "Residence Phone",
    "username",
    "Password",
    "is_active",
]
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def workbook(rows, *, shared=True, extra=None, numbers=()):
    """Build a small .xlsx by hand: shared strings, inline strings and plain numbers."""
    strings: list[str] = []
    body = []
    for number, row in enumerate(rows, start=1):
        cells = []
        for column, value in enumerate(row):
            ref = f"{chr(65 + column)}{number}"
            if value is None:
                continue
            if (number, column) in numbers:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            elif shared:
                strings.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        body.append(f'<row r="{number}">{"".join(cells)}</row>')
    parts = {
        "[Content_Types].xml": "<Types/>",
        "xl/workbook.xml": (
            f'<workbook xmlns="{SHEET_NS}" xmlns:r="{REL_NS}"><sheets>'
            '<sheet name="First" sheetId="1" r:id="rId7"/><sheet name="Other" sheetId="2" r:id="rId8"/>'
            "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId7" Target="worksheets/sheet3.xml"/>'
            '<Relationship Id="rId8" Target="worksheets/sheet4.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet3.xml": (
            f'<worksheet xmlns="{SHEET_NS}"><sheetData>{"".join(body)}</sheetData></worksheet>'
        ),
        "xl/worksheets/sheet4.xml": f'<worksheet xmlns="{SHEET_NS}"><sheetData/></worksheet>',
        "xl/sharedStrings.xml": (
            f'<sst xmlns="{SHEET_NS}">' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>"
        ),
        **(extra or {}),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as book:
        for name, content in parts.items():
            book.writestr(name, content)
    return buffer.getvalue()


PERSON = [
    "Rohit Deshpande",
    "Surface Engineering Division",
    "Thin Films Section",
    "00123",
    "",
    "4417",
    "Materials Group",
    None,
    "Rohit.Deshpande",
    None,
    None,
]


def parse(rows, **kw):
    return staff_sheet.parse(workbook(rows, **kw), DOMAIN)


def test_xlsx_cells_stay_text_and_the_first_sheet_is_found_through_its_relationship():
    rows = xlsx.read_rows(workbook([HEADER, PERSON]))
    assert rows[1][3] == "00123" and rows[1][8] == "Rohit.Deshpande"
    assert rows[1][7] == "" and len(rows[0]) == len(HEADER)


def test_inline_strings_and_numeric_cells_are_read_as_text():
    sheet = [HEADER, [*PERSON[:3], "1001", *PERSON[4:]]]
    inline = xlsx.read_rows(workbook(sheet, shared=False))
    assert inline[1][3] == "1001"
    numeric = xlsx.read_rows(workbook(sheet, numbers={(2, 3)}))
    assert numeric[1][3] == "1001"


def test_headers_ignore_case_spaces_and_underscores_and_blanks_take_their_defaults():
    header = ["FULL NAME", "Division", "SECTION", "emp_no", "E-mail", "extension", "group", "residence phone"]
    header += ["User Name", "password", "Is Active"]
    row = parse([header, PERSON])[0]
    assert (row.group, row.division, row.section) == (
        "Materials Group",
        "Surface Engineering Division",
        "Thin Films Section",
    )
    assert row.emp_no == "00123" and row.username == "rohit.deshpande"
    assert row.email == "rohit.deshpande@domain.in" and row.active is True and row.role == "member"
    assert row.password is None and row.residence_phone is None and row.errors == []


def test_an_unknown_column_is_named_in_plain_words():
    with pytest.raises(ApiError) as error:
        parse([[*HEADER, "Blood Group"], PERSON])
    assert "Blood Group" in error.value.message and error.value.code == "import_header"


def test_a_missing_required_column_is_refused():
    with pytest.raises(ApiError) as error:
        parse([[name for name in HEADER if name != "username"], PERSON[:10]])
    assert "username" in error.value.message


def test_group_is_the_only_placement_field_a_row_must_have():
    solo = ["Meera Nair", None, None, "7", None, None, "Materials Group", None, "meera.nair", None, None]
    assert parse([HEADER, solo])[0].errors == []
    for index, label in ((0, "full_name"), (3, "Emp No"), (6, "Group"), (8, "username")):
        broken = list(PERSON)
        broken[index] = None
        errors = parse([HEADER, broken])[0].errors
        assert any(label in text and "required" in text for text in errors), (label, errors)


def test_email_must_be_the_username_at_the_site_domain():
    wrong = list(PERSON)
    wrong[4] = "someone.else@domain.in"
    assert "must be rohit.deshpande@domain.in" in parse([HEADER, wrong])[0].errors[0]
    right = list(PERSON)
    right[4] = "Rohit.Deshpande@Domain.in"
    assert parse([HEADER, right])[0].errors == []


def test_flags_roles_and_repeats_are_checked_row_by_row():
    flag, role = list(PERSON), [*PERSON[:8], "other.person", None, "FALSE"]
    flag[10] = "maybe"
    assert "is_active" in parse([HEADER, flag])[0].errors[0]
    rows = parse([[*HEADER, "role"], [*role, "admin"], [*PERSON, "boss"], [*role, "member"]])
    assert rows[0].role == "admin" and rows[0].active is False
    assert "role must be" in rows[1].errors[0]
    assert "already appears on line 2" in " ".join(rows[2].errors)


def test_csv_with_the_same_headers_is_accepted():
    text = ",".join(HEADER) + "\r\n" + ",".join(c or "" for c in PERSON) + "\r\n"
    row = staff_sheet.parse(text.encode(), DOMAIN)[0]
    assert row.emp_no == "00123" and row.errors == []


def test_a_site_without_an_email_domain_cannot_check_addresses():
    with pytest.raises(ApiError) as error:
        staff_sheet.parse(workbook([HEADER, PERSON]), "")
    assert error.value.code == "email_domain_missing"


def test_files_that_are_not_workbooks_are_refused_kindly():
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(b"PK\x03\x04 this is not really a zip")
    assert error.value.code == "import_not_xlsx"
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    assert error.value.code == "import_encrypted" and "password" in error.value.message


def test_macro_workbooks_are_refused():
    book = workbook([HEADER, PERSON], extra={"xl/vbaProject.bin": "binary"})
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(book)
    assert error.value.code == "import_macros"


def test_zip_bombs_and_xml_entities_are_refused_before_they_expand():
    huge = workbook([HEADER], extra={"xl/media/blob.bin": "0" * (xlsx.MAX_PART + 10)})
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(huge)
    assert error.value.code == "import_unsafe"
    many = workbook([HEADER], extra={f"xl/extra/{n}.xml": "<a/>" for n in range(xlsx.MAX_ENTRIES + 1)})
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(many)
    assert error.value.code == "import_unsafe"
    lol = workbook(
        [HEADER], extra={"xl/sharedStrings.xml": '<!DOCTYPE x [<!ENTITY a "aaa">]><sst xmlns="x"/>'}
    )
    with pytest.raises(ApiError) as error:
        xlsx.read_rows(lol)
    assert error.value.code == "import_unsafe"


def test_a_big_upload_is_refused_by_size():
    with pytest.raises(importer.UploadTooLarge):
        staff_sheet.parse(b"PK\x03\x04" + b"0" * importer.MAX_BYTES, DOMAIN)


def test_the_template_writer_round_trips():
    rows = [list(staff_sheet.HEADERS), ["A & B", "", "", "00123"]]
    assert xlsx.read_rows(xlsx.write_rows(rows))[1][:4] == ["A & B", "", "", "00123"]
