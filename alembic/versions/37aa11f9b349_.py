"""empty message

Revision ID: 37aa11f9b349
Revises: 5580fff760e3
Create Date: 2024-07-17 23:47:19.757151

"""

from typing import Sequence, Union

import sqlalchemy as sa

from src import models

# revision identifiers, used by Alembic.
revision: str = "37aa11f9b349"
down_revision: Union[str, None] = "5580fff760e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with models.Session.begin() as session:
        session.merge(models.Job(id=models.DEFAULT_JOB))
        session.execute(sa.update(models.PlayerRound).values(job_id=models.DEFAULT_JOB))


def downgrade() -> None:
    pass
