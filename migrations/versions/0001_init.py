"""0001 建表：quotes 表（与 domain 无关，直接落 SQLAlchemy 模型）。"""

from __future__ import annotations

from alembic import op

from xianzhi.adapters.store import Base

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
