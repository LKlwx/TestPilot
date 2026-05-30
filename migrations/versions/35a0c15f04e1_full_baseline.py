"""full baseline

Revision ID: 35a0c15f04e1
Revises: 
Create Date: 2026-05-30 19:51:01.285867

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '35a0c15f04e1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('batch_result', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_batch_result_case_id', 'test_case', ['case_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('sys_operation_log', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_sys_op_log_user_id', 'user', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('sys_operation_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sys_op_log_user_id', type_='foreignkey')

    with op.batch_alter_table('batch_result', schema=None) as batch_op:
        batch_op.drop_constraint('fk_batch_result_case_id', type_='foreignkey')
