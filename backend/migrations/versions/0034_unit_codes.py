"""Short unique codes for organisation units (PO-19), backfilled from each unit's name."""

import re

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

FORMAT = "code ~ '^[A-Z0-9][A-Z0-9-]{1,23}$'"


def _base(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    code = "".join(word[0] for word in words).upper() or "UNIT"
    return code if len(code) > 1 else code + "U"


def upgrade():
    op.add_column("workspaces", sa.Column("code", sa.String(24)))
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("select id, name from workspaces where kind = 'org' order by created_at, id")
    ).all()
    taken: set[str] = set()
    for unit_id, name in rows:
        code, count = _base(name), 1
        while code in taken:
            count += 1
            code = f"{_base(name)}-{count}"
        taken.add(code)
        bind.execute(
            sa.text("update workspaces set code = :code where id = :id"), {"code": code, "id": unit_id}
        )
    op.create_check_constraint("ck_workspace_code_format", "workspaces", f"code is null or {FORMAT}")
    op.create_index(
        "uq_workspace_org_code",
        "workspaces",
        ["code"],
        unique=True,
        postgresql_where=sa.text("kind = 'org' AND code IS NOT NULL"),
    )


def _derived(name: str, code: str) -> bool:
    """True for a code that upgrade would regenerate from the name (so dropping it loses nothing)."""
    return re.fullmatch(re.escape(_base(name)) + r"(-\d+)?", code) is not None


def downgrade():
    rows = op.get_bind().execute(sa.text("select name, code from workspaces where code is not null")).all()
    if any(not _derived(name, code) for name, code in rows):
        raise RuntimeError("Chosen unit codes exist; downgrade would discard them")
    op.drop_index("uq_workspace_org_code", table_name="workspaces")
    op.drop_constraint("ck_workspace_code_format", "workspaces")
    op.drop_column("workspaces", "code")
