"""add_end_time_to_batchtask

Revision ID: 6525c2ed7c5b
Revises: f331bbaf6f81
Create Date: 2026-06-26 18:58:34.562569

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6525c2ed7c5b"
down_revision = "f331bbaf6f81"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("batch_task")]
    if "end_time" not in columns:
        with op.batch_alter_table("batch_task") as batch_op:
            batch_op.add_column(
                sa.Column("end_time", sa.DateTime(), nullable=True, comment="结束时间（所有 chunk 完成后记录）")
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("batch_task")]
    if "end_time" in columns:
        with op.batch_alter_table("batch_task") as batch_op:
            batch_op.drop_column("end_time")
