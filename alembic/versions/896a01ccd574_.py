"""empty message

Revision ID: 896a01ccd574
Revises: 1677d542b0f7
Create Date: 2024-07-18 16:14:35.032468

"""

from typing import Sequence, Union

from src import models

# revision identifiers, used by Alembic.
revision: str = "896a01ccd574"
down_revision: Union[str, None] = "1677d542b0f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with models.Session.begin() as session:
        for round in session.query(models.Round):
            if any(
                (
                    "All of the xenos were wiped out!" in round.round_end_text,
                    "Marine Major victory!" in round.round_end_text,
                    "The xenos hijacked a dropship" in round.round_end_text
                    and "but were wiped out by the marine" in round.round_end_text,
                    "The xeno hive was thrown into disarray after losing its xeno Queen!"
                    in round.round_end_text,
                ),
            ):
                round.winning_faction = "unmc"
            elif any(("All of the marines were wiped out!" in round.round_end_text,)):
                round.winning_faction = "xenonids"
            elif any(
                (("Mutual Annihilation!" in round.round_end_text),),
            ):
                round.winning_faction = None
            else:
                raise RuntimeError(
                    f"Unable to parse end round message, winner unknown: {round.id}, {round.round_end_text}"
                )
    pass


def downgrade() -> None:
    pass
