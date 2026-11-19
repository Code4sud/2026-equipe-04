"""quiz, mini-jeux et curseurs

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('game_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('youth_id', sa.Uuid(), nullable=False),
    sa.Column('instrument_id', sa.String(length=60), nullable=False),
    sa.Column('instrument_version', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('in_progress', 'completed', name='gamerunstatus', native_enum=False, create_constraint=True, length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('signals', sa.JSON(), nullable=False),
    sa.Column('metrics', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['youth_id'], ['users.id'], name=op.f('fk_game_runs_youth_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_game_runs'))
    )
    with op.batch_alter_table('game_runs', schema=None) as batch_op:
        batch_op.create_index('ix_game_runs_youth_instrument', ['youth_id', 'instrument_id'], unique=False)
        batch_op.create_index('uq_game_runs_one_open_per_instrument', ['youth_id', 'instrument_id'], unique=True, postgresql_where=sa.text("status = 'in_progress'"), sqlite_where=sa.text("status = 'in_progress'"))

    op.create_table('game_answers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.String(length=60), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('value', sa.JSON(), nullable=True),
    sa.Column('label', sa.Text(), nullable=True),
    sa.Column('skipped', sa.Boolean(), nullable=False),
    sa.Column('signals', sa.JSON(), nullable=False),
    sa.Column('response_ms', sa.Integer(), nullable=True),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('item_type', sa.String(length=20), nullable=True),
    sa.Column('item_scale', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['game_runs.id'], name=op.f('fk_game_answers_run_id_game_runs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_game_answers')),
    sa.UniqueConstraint('run_id', 'item_id', name=op.f('uq_game_answers_run_id'))
    )
    with op.batch_alter_table('game_answers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_game_answers_run_id'), ['run_id'], unique=False)

    op.create_table('game_facts',
    sa.Column('youth_id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('value', sa.String(length=160), nullable=False),
    sa.Column('original_value', sa.String(length=160), nullable=True),
    sa.Column('source_instrument_id', sa.String(length=60), nullable=True),
    sa.Column('source_item_id', sa.String(length=60), nullable=True),
    sa.Column('edited', sa.Boolean(), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['youth_id'], ['users.id'], name=op.f('fk_game_facts_youth_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('youth_id', 'key', name=op.f('pk_game_facts'))
    )
    op.create_table('game_trait_feedback',
    sa.Column('youth_id', sa.Uuid(), nullable=False),
    sa.Column('trait_id', sa.String(length=60), nullable=False),
    sa.Column('verdict', sa.String(length=10), nullable=False),
    sa.Column('label_at_verdict', sa.String(length=80), nullable=True),
    sa.Column('value_at_verdict', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['youth_id'], ['users.id'], name=op.f('fk_game_trait_feedback_youth_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('youth_id', 'trait_id', name=op.f('pk_game_trait_feedback'))
    )
    op.create_table('game_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('youth_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('subject', sa.String(length=160), nullable=False),
    sa.Column('before', sa.JSON(), nullable=True),
    sa.Column('after', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['youth_id'], ['users.id'], name=op.f('fk_game_events_youth_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_game_events'))
    )
    with op.batch_alter_table('game_events', schema=None) as batch_op:
        batch_op.create_index('ix_game_events_youth_created', ['youth_id', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('game_events', schema=None) as batch_op:
        batch_op.drop_index('ix_game_events_youth_created')

    op.drop_table('game_events')
    op.drop_table('game_trait_feedback')
    op.drop_table('game_facts')
    with op.batch_alter_table('game_answers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_answers_run_id'))

    op.drop_table('game_answers')
    with op.batch_alter_table('game_runs', schema=None) as batch_op:
        batch_op.drop_index('uq_game_runs_one_open_per_instrument', postgresql_where=sa.text("status = 'in_progress'"), sqlite_where=sa.text("status = 'in_progress'"))
        batch_op.drop_index('ix_game_runs_youth_instrument')

    op.drop_table('game_runs')
