import datetime
import os

import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

DB_URL = f'postgresql+psycopg://postgres:{os.environ["POSTGRES_PASSWORD"]}@{os.environ["PGHOST"]}:{os.environ["PGPORT"]}/postgres'
engine = sa.create_engine(DB_URL)
Session = sa_orm.sessionmaker(engine)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = sa.MetaData(naming_convention=convention)

DEFAULT_JOB = "CMRifleman"
DEFAULT_WINNING_FACTION = "unmc"


class Base(sa_orm.DeclarativeBase):
    metadata = metadata


class Map(Base):
    __tablename__ = "maps"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.BigInteger, primary_key=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text(), unique=True)


class Faction(Base):
    __tablename__ = "factions"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.BigInteger, primary_key=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text(), unique=True)


class Job(Base):
    __tablename__ = "jobs"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.BigInteger, primary_key=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text(), unique=True)
    faction_id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.ForeignKey("factions.id"))


class Player(Base):
    __tablename__ = "players"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.BigInteger, primary_key=True)
    guid: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text(), unique=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text())


class Round(Base):
    __tablename__ = "rounds"
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.BigInteger, primary_key=True)
    created_at: sa_orm.Mapped[datetime.datetime] = sa_orm.mapped_column(
        sa.types.DateTime(timezone=True),
        default=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    map_id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.ForeignKey("maps.id"), nullable=True
    )
    winning_faction_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.ForeignKey("factions.id"), nullable=True
    )


class PlayerRound(Base):
    __tablename__ = "players_rounds"
    __table_args__ = (sa.UniqueConstraint("player_id", "round_id"),)
    id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, primary_key=True, autoincrement=True
    )
    player_id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.ForeignKey("players.id"))
    round_id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.ForeignKey("rounds.id"))
    job_id: sa_orm.Mapped[int] = sa_orm.mapped_column(sa.ForeignKey("jobs.id"))
