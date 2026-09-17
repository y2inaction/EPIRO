"""Make story status a real enum.

Story status was free text, and the only value anything ever wrote was
"published": approval and publication were the same act, and no state existed
between drafting and going public. The enum names the editorial states spec
section 36 requires so the transitions can be enforced.

The cast is deliberately strict. Any value that is not one of the six states
aborts the migration rather than being folded into "draft": quietly
reclassifying an editorial record would be worse than failing.

Revision ID: c2b0d6a76a04
Revises: 2f8ad0bf8ffa
Create Date: 2026-09-17 13:13:36.799966

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2b0d6a76a04'
down_revision: Union[str, None] = '2f8ad0bf8ffa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = ("draft", "in_review", "approved", "rejected", "published", "archived")


def upgrade() -> None:
    # Autogenerate emits alter_column alone, which cannot work: the type does
    # not exist yet, and Postgres will not cast varchar to an enum without an
    # explicit USING clause.
    values = ", ".join(f"'{status}'" for status in STATUSES)
    op.execute(f"CREATE TYPE storystatus AS ENUM ({values})")
    op.execute(
        "ALTER TABLE story ALTER COLUMN status TYPE storystatus "
        "USING status::storystatus"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE story ALTER COLUMN status TYPE VARCHAR(50) "
        "USING status::text"
    )
    op.execute("DROP TYPE IF EXISTS storystatus")
