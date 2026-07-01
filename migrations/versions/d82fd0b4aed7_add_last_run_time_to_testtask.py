"""add_last_run_time_to_testtask

Revision ID: d82fd0b4aed7
Revises: 6525c2ed7c5b
Create Date: 2026-06-29 12:29:45.957014

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d82fd0b4aed7"
down_revision = "6525c2ed7c5b"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("test_task")]
    if "last_run_time" not in columns:
        with op.batch_alter_table("test_task") as batch_op:
            batch_op.add_column(sa.Column("last_run_time", sa.DateTime(), nullable=True, comment="最近一次执行时间"))
            batch_op.add_column(
                sa.Column(
                    "last_status",
                    sa.String(length=20),
                    nullable=True,
                    comment="最近一次执行状态：success/partial/empty",
                )
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("test_task")]
    if "last_run_time" in columns:
        with op.batch_alter_table("test_task") as batch_op:
            batch_op.drop_column("last_status")
            batch_op.drop_column("last_run_time")
