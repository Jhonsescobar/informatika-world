"""Ujian terhubung ke komponen nilai dan tahun ajaran

Revision ID: c3e9a1d07b52
Revises: b8d52e7c1f34
Create Date: 2026-11-07 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e9a1d07b52'
down_revision: Union[str, Sequence[str], None] = 'b8d52e7c1f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exams', sa.Column('component_id', sa.Integer(), nullable=True))
    op.add_column('exams', sa.Column('academic_year_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_exams_component', 'exams', 'score_components', ['component_id'], ['id'])
    op.create_foreign_key('fk_exams_academic_year', 'exams', 'academic_years', ['academic_year_id'], ['id'])
    # Ujian lama dianggap milik tahun ajaran aktif
    op.execute("""
        UPDATE exams SET academic_year_id = (
            SELECT id FROM academic_years WHERE is_active = 1 ORDER BY id DESC LIMIT 1)
    """)
    # Versi lama membuat komponen otomatis bernama sama dengan judul ujian: sambungkan
    op.execute("""
        UPDATE exams e SET component_id = (
            SELECT c.id FROM score_components c
            WHERE c.name = e.title AND c.class_target = e.class_target
            ORDER BY c.id LIMIT 1)
    """)


def downgrade() -> None:
    op.drop_constraint('fk_exams_academic_year', 'exams', type_='foreignkey')
    op.drop_constraint('fk_exams_component', 'exams', type_='foreignkey')
    op.drop_column('exams', 'academic_year_id')
    op.drop_column('exams', 'component_id')
