"""Staff-list CSV parsing: shape, encoding, limits and formula-like text (no database)."""

import pytest

from labadda.changes import importer
from labadda.errors import Invalid

HEAD = "employee_no,username,display_name,designation,unit_code,role,status,effective_on\n"


def parse(text: str | bytes):
    return importer.parse(text.encode() if isinstance(text, str) else text)


def test_template_round_trips_and_bom_is_tolerated():
    rows = parse(importer.TEMPLATE)
    assert len(rows) == 1 and rows[0].errors == []
    assert rows[0].username == "example.person" and rows[0].unit_code == "TF"
    assert rows[0].effective_on.isoformat() == "2026-12-01"
    assert parse("﻿" + HEAD + ",gita,Gita Sen,,CS,,,\n")[0].display_name == "Gita Sen"


def test_row_errors_carry_line_numbers_and_plain_words():
    rows = parse(
        HEAD + ",ok.one,Ok One,,CS,member,,\n,Bad Name,X,,,boss,gone,12/31/2026\n,short,Y,,,,,\n,a,b\n"
    )
    assert rows[0].errors == [] and rows[0].line == 2
    bad = rows[1]
    assert bad.line == 3 and len(bad.errors) == 4
    assert any("username" in e for e in bad.errors) and any("effective_on" in e for e in bad.errors)
    assert rows[3].errors == ["This line has 3 cells but the first line has 8."]


def test_repeated_username_and_employee_number_are_flagged_on_the_later_line():
    rows = parse(HEAD + "E1,gita,Gita,,CS,,,\nE1,Gita,Gita again,,CS,,,\n,hari,Hari,,CS,,,\n")
    assert rows[0].errors == []
    assert "line 2" in rows[1].errors[0] and len(rows[1].errors) == 2
    assert rows[2].errors == []


@pytest.mark.parametrize("cell", ["=1+1", "+cmd", "-5", "@SUM(A1)", "＝HYPERLINK(x)"])
def test_formula_like_cells_are_kept_as_text_with_a_notice(cell):
    row = parse(HEAD + f",gita,{cell},,CS,,,\n")[0]
    assert row.display_name == cell and row.errors == []
    assert row.warnings and "plain text" in row.warnings[0]


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "import_empty"),
        (b"   \n", "import_empty"),
        (HEAD.encode(), "import_empty"),
        (b"PK\x03\x04\x00\x00binary", "import_not_csv"),
        (b"username,display_name\n\xff\xfe,x\n", "import_encoding"),
        (b"username,colour\ngita,red\n", "import_header"),
        (b"username,username\ngita,gita\n", "import_header"),
        (b"display_name\nGita\n", "import_header"),
        (b'username\n"unterminated\n', "import_not_csv"),
    ],
)
def test_file_level_problems_are_refused_before_any_row_is_read(data, code):
    with pytest.raises(Invalid) as caught:
        parse(data)
    assert caught.value.code == code


def test_size_and_row_limits():
    with pytest.raises(importer.UploadTooLarge):
        parse(b"username\n" + b"x" * importer.MAX_BYTES)
    many = "username\n" + "".join(f"user{n:04d}\n" for n in range(importer.MAX_ROWS + 1))
    with pytest.raises(importer.UploadTooLarge):
        parse(many)
    assert len(parse("username\n" + "".join(f"user{n:04d}\n" for n in range(importer.MAX_ROWS)))) == 2000


def test_overlong_and_control_character_cells_are_row_errors():
    long = "x" * 201
    rows = parse(f"username,display_name\ngita,{long}\nhari,\"Ha\x07ri\"\n")
    assert "longer than" in rows[0].errors[0]
    assert "control characters" in rows[1].errors[0]
