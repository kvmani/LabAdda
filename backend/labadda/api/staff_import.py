"""Administrator-only Excel staff import: review a sheet, then apply it all or not at all."""

from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, Response
from psycopg.errors import QueryCanceled
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..changes import importer, service, staff_import, staff_sheet, xlsx
from ..deps import Actor, get_db, get_settings, require_console
from ..errors import ApiError, Invalid

router = APIRouter(prefix="/admin/changes/import/staff", tags=["people changes"])
console_people_admin = require_console("people")
SHEET_TYPES = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/octet-stream",
)


def _unavailable(db: Session, error: DBAPIError) -> ApiError:
    db.rollback()
    if isinstance(error.orig, QueryCanceled):
        return service.TooLong()
    return ApiError("changes_unavailable", "Staff changes are unavailable. Try again.", status=503)


async def _read_sheet(request: Request) -> bytes:
    """Refuse a wrong type or oversized body before reading it all; the bytes are never stored."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() not in SHEET_TYPES:
        raise Invalid("import_not_xlsx", "Upload an Excel workbook (.xlsx) or a CSV file (.csv).")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > importer.MAX_BYTES:
        raise importer.UploadTooLarge()
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > importer.MAX_BYTES:
            raise importer.UploadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/template")
def template(request: Request, actor: Actor = Depends(console_people_admin)) -> Response:
    """The exact headers and one fictional example row, as an Excel workbook."""
    domain = get_settings(request).email_domain or "domain.in"
    example = [
        "Ananya Iyer",
        "Surface Engineering Division",
        "Thin Films Section",
        "00123",
        f"ananya.iyer@{domain}",
        "4417",
        "Materials Group",
        "",
        "ananya.iyer",
        "",
        "TRUE",
        "member",
    ]
    return Response(
        xlsx.write_rows([list(staff_sheet.HEADERS), example]),
        media_type=SHEET_TYPES[0],
        headers={
            "Content-Disposition": 'attachment; filename="staff-import-template.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/preview")
async def preview(
    request: Request,
    actor: Actor = Depends(console_people_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Read a sheet and say what would be created, and what is wrong; nothing is written."""
    data = await _read_sheet(request)
    try:
        return await run_in_threadpool(staff_import.preview, db, actor, get_settings(request), data)
    except DBAPIError as error:
        raise _unavailable(db, error) from None


@router.post("/apply")
async def apply(
    request: Request,
    actor: Actor = Depends(console_people_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Read the same sheet again and create everything, or nothing; the reason travels in a header."""
    data = await _read_sheet(request)
    digest = request.headers.get("x-import-digest", "")
    reason = unquote(request.headers.get("x-import-reason", ""))
    try:
        return await run_in_threadpool(
            staff_import.apply,
            db,
            actor,
            get_settings(request),
            data,
            digest,
            reason,
            request.app.state.hub,
        )
    except DBAPIError as error:
        raise _unavailable(db, error) from None
