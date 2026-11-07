"""Kisi-kisi materi, remedial, dan catatan anti-cheat

Revision ID: a7c41f2e9b10
Revises: 18b2be27063a
Create Date: 2026-11-07 19:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c41f2e9b10'
down_revision: Union[str, Sequence[str], None] = '18b2be27063a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('materials', sa.Column('close_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table('remedial_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id']),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_remedial_requests_id'), 'remedial_requests', ['id'], unique=False)

    op.create_table('exam_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_exam_violations_id'), 'exam_violations', ['id'], unique=False)
    op.create_index(op.f('ix_exam_violations_session_id'), 'exam_violations', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exam_violations_session_id'), table_name='exam_violations')
    op.drop_index(op.f('ix_exam_violations_id'), table_name='exam_violations')
    op.drop_table('exam_violations')
    op.drop_index(op.f('ix_remedial_requests_id'), table_name='remedial_requests')
    op.drop_table('remedial_requests')
    op.drop_column('materials', 'close_at')
    op.drop_column('materials', 'is_published')
