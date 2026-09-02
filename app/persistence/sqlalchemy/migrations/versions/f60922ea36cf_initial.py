"""initial schema

Revision ID: f60922ea36cf
Revises:
Create Date: 2026-09-01 13:47:54.492453

"""

from typing import Sequence, Union

from alembic import op

revision: str = "f60922ea36cf"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.persistence.sqlalchemy.base import Base
    import app.persistence.sqlalchemy.models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.persistence.sqlalchemy.base import Base
    import app.persistence.sqlalchemy.models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind())
