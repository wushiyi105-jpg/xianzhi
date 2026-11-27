"""0001：报价表；显式建表，不用 create_all。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item", sa.String(length=300), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("anchor", sa.String(length=16), nullable=False),
        sa.Column("suggested_cents", sa.Integer(), nullable=False),
        sa.Column("low_cents", sa.Integer(), nullable=False),
        sa.Column("high_cents", sa.Integer(), nullable=False),
        sa.Column("floor_cents", sa.Integer(), nullable=False),
        sa.Column("net_json", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotes_model", "quotes", ["model"])


def downgrade() -> None:
    op.drop_index("ix_quotes_model", table_name="quotes")
    op.drop_table("quotes")
