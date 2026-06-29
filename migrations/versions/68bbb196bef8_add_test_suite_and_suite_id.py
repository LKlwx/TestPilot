"""add_test_suite_and_suite_id

Revision ID: 68bbb196bef8
Revises: d82fd0b4aed7
Create Date: 2026-06-29 13:13:20.768940

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68bbb196bef8'
down_revision = 'd82fd0b4aed7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'test_suite' not in existing_tables:
        op.create_table('test_suite',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('creator_id', sa.Integer(), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
    if 'suite_case_association' not in existing_tables:
        op.create_table('suite_case_association',
        sa.Column('suite_id', sa.Integer(), nullable=False),
        sa.Column('case_type', sa.String(length=20), nullable=False, default='api', comment='用例类型: api/ui/perf'),
        sa.Column('case_id', sa.Integer(), nullable=False, comment='对应类型的用例ID'),
        sa.ForeignKeyConstraint(['suite_id'], ['test_suite.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('suite_id', 'case_type', 'case_id')
        )

    columns = [c['name'] for c in inspector.get_columns('test_task')]
    if 'suite_id' not in columns:
        with op.batch_alter_table('test_task') as batch_op:
            batch_op.add_column(sa.Column('suite_id', sa.Integer(), nullable=True, comment='关联套件ID'))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('test_task')]
    if 'suite_id' in columns:
        with op.batch_alter_table('test_task') as batch_op:
            batch_op.drop_column('suite_id')

    existing_tables = inspector.get_table_names()
    if 'suite_case_association' in existing_tables:
        op.drop_table('suite_case_association')
    if 'test_suite' in existing_tables:
        op.drop_table('test_suite')
