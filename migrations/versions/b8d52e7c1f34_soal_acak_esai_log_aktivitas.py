"""Soal acak per siswa, soal esai, dan log aktivitas ujian

Revision ID: b8d52e7c1f34
Revises: a7c41f2e9b10
Create Date: 2026-11-07 19:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8d52e7c1f34'
down_revision: Union[str, Sequence[str], None] = 'a7c41f2e9b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exams', sa.Column('question_count', sa.Integer(), nullable=True))
    op.add_column('exam_sessions', sa.Column('question_ids', sa.Text(), nullable=True))
    op.add_column('questions', sa.Column('question_type', sa.String(), nullable=False, server_default='pg'))
    op.add_column('questions', sa.Column('answer_key', sa.Text(), nullable=True))
    op.add_column('questions', sa.Column('keywords', sa.Text(), nullable=True))
    op.add_column('exam_answers', sa.Column('answer_text', sa.Text(), nullable=True))
    op.add_column('exam_answers', sa.Column('similarity', sa.Float(), nullable=True))
    op.add_column('exam_answers', sa.Column('auto_points', sa.Float(), nullable=True))
    op.add_column('exam_answers', sa.Column('manual_points', sa.Float(), nullable=True))
    op.create_table('exam_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('option_id', sa.Integer(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_exam_events_id'), 'exam_events', ['id'], unique=False)
    op.create_index(op.f('ix_exam_events_session_id'), 'exam_events', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exam_events_session_id'), table_name='exam_events')
    op.drop_index(op.f('ix_exam_events_id'), table_name='exam_events')
    op.drop_table('exam_events')
    for kolom in ('manual_points', 'auto_points', 'similarity', 'answer_text'):
        op.drop_column('exam_answers', kolom)
    for kolom in ('keywords', 'answer_key', 'question_type'):
        op.drop_column('questions', kolom)
    op.drop_column('exam_sessions', 'question_ids')
    op.drop_column('exams', 'question_count')
