"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-01 15:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. candidates table
    op.create_table(
        'candidates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('resume_text', sa.Text(), nullable=False, comment='Full extracted raw text from the candidate resume'),
        sa.Column('extracted_skills', sa.JSON(), nullable=True, comment='Structured JSON of candidate skills, experience years, technologies'),
        sa.Column('target_role', sa.String(length=120), nullable=False, comment='Target job role (e.g., Backend Engineer, Data Scientist)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_candidates_id'), 'candidates', ['id'], unique=False)
    op.create_index(op.f('ix_candidates_target_role'), 'candidates', ['target_role'], unique=False)

    # 2. sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=120), nullable=False, comment='Specific role being screened for during this session'),
        sa.Column('status', sa.String(length=50), nullable=False, comment='Session status: pending, in_progress, completed, failed, evaluated'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessions_id'), 'sessions', ['id'], unique=False)
    op.create_index(op.f('ix_sessions_candidate_id'), 'sessions', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_sessions_role'), 'sessions', ['role'], unique=False)
    op.create_index(op.f('ix_sessions_status'), 'sessions', ['status'], unique=False)

    # 3. questions table
    op.create_table(
        'questions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False, comment='Generated role-based screening question'),
        sa.Column('source_chunk_ids', sa.JSON(), nullable=True, comment='List of ChromaDB chunk IDs referenced to synthesize this question'),
        sa.Column('topic', sa.String(length=100), nullable=False, comment='Domain topic e.g. System Design, Concurrency, SQL, Machine Learning'),
        sa.Column('difficulty', sa.String(length=50), nullable=False, comment='Difficulty rating: easy, medium, hard'),
        sa.Column('order_index', sa.Integer(), nullable=False, comment='Sequence index within the screening session'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_questions_id'), 'questions', ['id'], unique=False)
    op.create_index(op.f('ix_questions_session_id'), 'questions', ['session_id'], unique=False)
    op.create_index(op.f('ix_questions_topic'), 'questions', ['topic'], unique=False)

    # 4. answers table
    op.create_table(
        'answers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('question_id', sa.String(length=36), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False, comment="Candidate's submitted response text"),
        sa.Column('evaluation', sa.JSON(), nullable=True, comment='AI Evaluation output (score, rubric checks, strengths, weaknesses, followups)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_answers_id'), 'answers', ['id'], unique=False)
    op.create_index(op.f('ix_answers_question_id'), 'answers', ['question_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_answers_question_id'), table_name='answers')
    op.drop_index(op.f('ix_answers_id'), table_name='answers')
    op.drop_table('answers')

    op.drop_index(op.f('ix_questions_topic'), table_name='questions')
    op.drop_index(op.f('ix_questions_session_id'), table_name='questions')
    op.drop_index(op.f('ix_questions_id'), table_name='questions')
    op.drop_table('questions')

    op.drop_index(op.f('ix_sessions_status'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_role'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_candidate_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_id'), table_name='sessions')
    op.drop_table('sessions')

    op.drop_index(op.f('ix_candidates_target_role'), table_name='candidates')
    op.drop_index(op.f('ix_candidates_id'), table_name='candidates')
    op.drop_table('candidates')
