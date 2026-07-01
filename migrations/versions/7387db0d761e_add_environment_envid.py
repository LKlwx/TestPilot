"""add_environment_envid

Revision ID: 7387db0d761e
Revises: 9fe14fa34fc5
Create Date: 2026-06-25 20:44:54.668315

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7387db0d761e"
down_revision = "9fe14fa34fc5"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "environment" not in existing_tables:
        op.create_table(
            "environment",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False, comment="环境名称，如 开发环境/测试环境/生产环境"),
            sa.Column(
                "base_url", sa.String(length=500), nullable=False, comment="环境基地址，如 http://dev-server:8080"
            ),
            sa.Column("headers", sa.Text(), nullable=True, comment="全局请求头，JSON 对象"),
            sa.Column("variables", sa.Text(), nullable=True, comment="环境变量，JSON 对象，如 {'token': 'xxx'}"),
            sa.Column("is_default", sa.Boolean(), nullable=True, comment="是否为默认环境"),
            sa.Column("create_time", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    for table in ["performance_case", "test_case", "ui_case"]:
        columns = [c["name"] for c in inspector.get_columns(table)]
        if "env_id" not in columns:
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(sa.Column("env_id", sa.Integer(), nullable=True, comment="所属环境ID"))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for table in ["ui_case", "test_case", "performance_case"]:
        columns = [c["name"] for c in inspector.get_columns(table)]
        if "env_id" in columns:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("env_id")

    existing_tables = inspector.get_table_names()
    if "environment" in existing_tables:
        op.drop_table("environment")
    # ### end Alembic commands ###
