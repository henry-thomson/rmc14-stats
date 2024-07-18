"""empty message

Revision ID: fa2683367f41
Revises: 1bb60c675bf1
Create Date: 2024-07-18 21:32:36.065452

"""

from typing import Sequence, Union

from src import models

# revision identifiers, used by Alembic.
revision: str = "fa2683367f41"
down_revision: Union[str, None] = "1bb60c675bf1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with models.Session.begin() as session:
        session.add(models.Faction(name="xenonids"))
        session.add(models.Faction(name="unmc"))
        session.add(models.Faction(name="none"))


def downgrade() -> None:
    pass
