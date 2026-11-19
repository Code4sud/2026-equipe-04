"""fusion : jeu et historique des talents

Les tables du jeu (0002) et l'historique des talents (talent_history) partent toutes deux de
0001 et ne se touchent pas : cette révision réunit les deux branches sans rien changer.

Revision ID: 0003
Revises: 0002, talent_history
Create Date: 2026-11-19 09:00:00.000000

"""


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = ('0002', 'talent_history')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
