import datetime
import re
import typing as t

import requests
import unzip_http  # type: ignore
import yaml
from loguru import logger

from src import models

ROOT_URL = "https://replays.rouny-ss14.com/replays/alamo"
HREF_FINDER = re.compile(r'<a href="([\d]+)\/">')
REPLAY_FINDER = re.compile(r'<a href="([^"]+\.zip)">')
TIMEOUT = 5

RoundSummary = t.Dict[str, t.Any]


class ExtractOutput(t.TypedDict):
    date: datetime.datetime
    data: RoundSummary


class TransformOutput(t.TypedDict):
    date: datetime.datetime
    map: str
    winning_faction: str | None
    players: list[dict[str, str]]
    round_id: int


class Replays:
    @property
    def _replay_urls(self):
        # TODO: Extract files in reversed order so that if we hit ones we already have
        # we can stop early.
        response = requests.get(ROOT_URL, timeout=TIMEOUT)
        for year in HREF_FINDER.finditer(response.text):
            year = year.group(1)
            response = requests.get(f"{ROOT_URL}/{year}/", timeout=TIMEOUT)
            for month in HREF_FINDER.finditer(response.text):
                month = month.group(1)
                response = requests.get(f"{ROOT_URL}/{year}/{month}/", timeout=TIMEOUT)
                for day in HREF_FINDER.finditer(response.text):
                    day = day.group(1)
                    response = requests.get(
                        f"{ROOT_URL}/{year}/{month}/{day}/", timeout=TIMEOUT
                    )
                    for replay in REPLAY_FINDER.finditer(response.text):
                        replay = replay.group(1)
                        replay_url = f"{ROOT_URL}/{year}/{month}/{day}/{replay}"
                        yield replay_url

    def _extract(self) -> t.Iterator[ExtractOutput]:
        for replay_url in self._replay_urls:
            year, month, day = replay_url.split("/")[-1].split("-")[0].split("_")
            hour, minute = replay_url.split("/")[-1].split("-")[1].split("_")
            date = datetime.datetime(
                year=int(year),
                month=int(month),
                day=int(day),
                hour=int(hour),
                minute=int(minute),
            )

            try:
                logger.info(f"Downloading {replay_url}")
                remote_zip_file = unzip_http.RemoteZipFile(replay_url)

                data = yaml.safe_load(
                    remote_zip_file.open_text("_replay/replay_final.yml").read()  # type: ignore
                )
                if data is None:
                    logger.warning(f"Missing summary data {replay_url}")
                    continue
                if data["roundEndText"] is None:
                    logger.warning(f"Missing round end text {replay_url}")
                    continue

                yield {"date": date, "data": data}
            except Exception:
                logger.warning(f"Bad zip file {replay_url}")

    def _transform(
        self,
        extract_output: ExtractOutput,
    ) -> TransformOutput:
        date = extract_output["date"]
        data = extract_output["data"]

        map_str = None
        try:
            map_str = data["maps"][1]
        except (KeyError, TypeError):
            map_str = data["map"]
        if map_str == "Solaris":
            map_str = "Solaris Ridge"
        if map_str == "Almayer":
            map_str = "LV624"

        players: list[dict[str, str]] = [
            {
                "id": x["playerGuid"],
                "job": x["jobPrototypes"][0]
                if len(x["jobPrototypes"]) > 0
                else models.DEFAULT_JOB,
                "ic_name": x["playerICName"],
                "ooc_name": x["playerOOCName"],
            }
            for x in data["roundEndPlayers"]
        ]

        if any(
            (
                "All of the xenos were wiped out!" in data["roundEndText"],
                "Marine Major victory!" in data["roundEndText"],
                "The xenos hijacked a dropship" in data["roundEndText"]
                and "but were wiped out by the marine" in data["roundEndText"],
                "The xeno hive was thrown into disarray after losing its xeno Queen!"
                in data["roundEndText"],
            ),
        ):
            winning_faction = "unmc"
        elif any(("All of the marines were wiped out!" in data["roundEndText"],)):
            winning_faction = "xenoids"
        elif any(
            (("Mutual Annihilation!" in data["roundEndText"]),),
        ):
            winning_faction = None
        else:
            raise RuntimeError(
                f"Unable to parse end round message, winner unknown: {data['roundEndText']}"
            )

        round_id = int(data["roundId"])

        return {
            "date": date,
            "map": map_str,
            "round_id": round_id,
            "winning_faction": winning_faction,
            "players": players,
        }

    def _load(self, transform_output: TransformOutput):
        with models.Session.begin() as session:
            map_ = session.merge(models.Map(id=transform_output["map"]))

            # if session.query(models.Round).get(transform_output["round_id"]):
            #     return

            round_ = session.merge(
                models.Round(
                    id=transform_output["round_id"],
                    map=map_.id,
                    winning_faction=transform_output["winning_faction"],
                    created_at=transform_output["date"],
                )
            )

            for raw_player in transform_output["players"]:
                job = session.merge(models.Job(id=raw_player["job"]))

                player = session.merge(
                    models.Player(
                        id=raw_player["id"],
                        name=raw_player["ooc_name"],
                    )
                )
                player_round = (
                    session.query(models.PlayerRound)
                    .filter(
                        models.PlayerRound.player_id == player.id,
                        models.PlayerRound.round_id == round_.id,
                    )
                    .first()
                )
                if player_round:
                    player_round.job_id = raw_player["job"]
                else:
                    session.add(
                        models.PlayerRound(
                            player_id=player.id,
                            round_id=round_.id,
                            job_id=job.id,
                        )
                    )

    def process(self):
        for extract_output in self._extract():
            transform_output = self._transform(extract_output)
            if not transform_output:
                continue
            self._load(transform_output)


replays = Replays()
replays.process()
