"""empty message

Revision ID: c3bf7160a888
Revises: be0462ce33d4
Create Date: 2024-07-18 22:29:24.731246

"""

from typing import Sequence, Union


from src import models

# revision identifiers, used by Alembic.
revision: str = "c3bf7160a888"
down_revision: Union[str, None] = "be0462ce33d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with models.Session.begin() as session:
        for round in session.query(models.Round):
            round.map_id = round.map  # type: ignore


def downgrade() -> None:
    pass
