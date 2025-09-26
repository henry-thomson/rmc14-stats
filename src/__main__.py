import datetime
import os
import re
import typing as t

import requests
import unzip_http  # type: ignore
import yaml
import json
from pathlib import Path
from html.parser import HTMLParser
from loguru import logger

GITHUB_ACTION = os.getenv("GITHUB_ACTION")

if GITHUB_ACTION != "true":
    from src import models

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk

    from src import __version__

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        release=__version__,
    )

ROOT_URL = "https://replays.rouny-ss14.com/replays/alamo/"
HREF_FINDER = re.compile(r'<a href="([\d]+)\/">')
REPLAY_FINDER = re.compile(r'<a href="([^"]+\.zip)">')
TIMEOUT = 5
BACKFILL_DAYS = 7

RoundSummary = t.Dict[str, t.Any]



# OLD BACKUP is just a safe guard against me doing something dumb, and replacing the old links with current
# OLD is a list of zip links that were collected and processed, basically all the stuff that is in the DB already
# PREVIOUS is a list of zip links that got collected in the previous CI run, did get downloaded, but were not added into the DB
# CURRENT is a list ALL zip links that got collected right now
# NEW is a difference between PREVIOUS and CURRENT, ie. links that are new, and were not even downloaded
OLD_REPLAY_LINKS_BACKUP = "oldReplayLinksBackup.json"
OLD_REPLAY_LINKS = "oldReplayLinks.json"
PREVIOUS_REPLAY_LINKS = "previousReplayLinks.json"

CURRENT_REPLAY_LINKS = "currentReplayLinks.json" # technically never used just keeping it as a documentation
NEW_REPLAY_LINKS = "newReplayLinks.json" # technically never used just keeping it as a documentation

# CURRENT - OLD = all the files that were not added to the DB yet, basically all the files in `data/yaml` folder
# CURRENT - PREVIOUS = all the files that i am about to download, that got created since the previous run


CURRENT_FILE_PARENT = Path(Path(__file__).parent)
IN_DOCKER = os.getenv("IN_DOCKER")


class LinkHTMLParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.crawlerPaths = []

    # Find every anchor tag in the current HTML page
    def handle_starttag(self, tag, attributes):
        if tag == "a" and attributes[0][0] == "href":
            self.crawlerPaths.append(attributes[0][1])



class ExtractOutput(t.TypedDict):
    date: datetime.datetime
    data: RoundSummary


class TransformOutput(t.TypedDict):
    date: datetime.datetime
    map: str
    winning_faction: str
    winning_score: float
    players: list[dict[str, str]]
    round_id: int
    summary_message: str


class Replays:

    def __init__(self):
        self.oldReplayLinks = []
        self.previousReplayLinks = []
        self.currentReplayLinks = []
        self.newReplayLinks = []

    @property
    def _replay_urls(self):
        response = requests.get(ROOT_URL, timeout=TIMEOUT)
        for year in reversed(list(HREF_FINDER.finditer(response.text))):
            year = year.group(1)
            response = requests.get(f"{ROOT_URL}/{year}/", timeout=TIMEOUT)
            for month in reversed(list(HREF_FINDER.finditer(response.text))):
                month = month.group(1)
                response = requests.get(f"{ROOT_URL}/{year}/{month}/", timeout=TIMEOUT)
                for day in reversed(list(HREF_FINDER.finditer(response.text))):
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
            # Do not process records older then a week.
            if date < datetime.datetime.now() - datetime.timedelta(days=BACKFILL_DAYS):
                # Next records are too old, don't need any of those.
                logger.info("Skipping the rest of records as they are too old.")
                break

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


    # Same as _extract, but goes through every file in src/data/yaml, and reads the them
    def _extractFromLocal(self) -> t.Iterator[ExtractOutput]:
        for localFilePath in Path( CURRENT_FILE_PARENT / "data" / "yaml/").iterdir():
            year, month, day = localFilePath.name.split("-")[0].split("_")
            hour, minute = localFilePath.name.split("-")[1].split("_")
            date = datetime.datetime(
                year=int(year),
                month=int(month),
                day=int(day),
                hour=int(hour),
                minute=int(minute),
            )
            try:
                with localFilePath.open("r") as f:
                    logger.info(f"Loading from file {localFilePath}")
                    data = yaml.safe_load(f)

                    if data is None:
                        logger.warning(f"Missing summary data {localFilePath}")
                        continue
                    if data["roundEndText"] is None:
                        logger.warning(f"Missing round end text {localFilePath}")
                        continue

                    yield {"date": date, "data": data}
            except Exception as e:
                logger.warning(f"{e} == at file == {localFilePath}")


    def _transform(
        self,
        extract_output: ExtractOutput,
    ) -> TransformOutput:
        date = extract_output["date"]
        data = extract_output["data"]

        map_str = None
        try:
            map_str = data["maps"][1]
        except (KeyError, TypeError, IndexError):
            try:
                map_str = data["maps"][0]
            except KeyError:
                map_str = data["map"]

        players: list[dict[str, str]] = [
            {
                "id": x["playerGuid"],
                "job": x["jobPrototypes"][0]
                if len(x["jobPrototypes"]) > 0
                else models.DEFAULT_JOB,
                "ic_name": x["playerICName"],
                "ooc_name": x["playerOOCName"],
                "faction": "xenonids"
                if len(x["jobPrototypes"]) > 0
                and x["jobPrototypes"][0].startswith("CMXeno")
                else "unmc",
            }
            for x in data["roundEndPlayers"]
            if x["playerOOCName"] != "(IMPOSSIBLE: REGISTERED MIND WITH NO OWNER)"
        ]

        # Xeno minor.
        if (
            "The xenos hijacked a dropship" in data["roundEndText"]
            and "but were wiped out by the marine" in data["roundEndText"]
        ):
            winning_faction = "xenonids"
            winning_score = 0  # don't care about minor wins atm
        # Xeno major.
        elif "All of the marines were wiped out!" in data["roundEndText"]:
            winning_faction = "xenonids"
            winning_score = 1
        # Marine minor.
        elif any(
            (
                "The xeno hive was thrown into disarray after losing its xeno Queen!"
                in data["roundEndText"],
                # No idea what the heck this one is, so just assiming it's a minor win
                # and assigning no score to it.
                "VIP" in data["roundEndText"],
                "PMC" in data["roundEndText"],
            )
        ):
            winning_faction = "unmc"
            winning_score = 0  # don't care about minor wins atm
        # Marine major.
        elif any(
            (
                "All of the xenos were wiped out!" in data["roundEndText"],
                "The xeno hive was wiped out!" in data["roundEndText"],
                "Marine Major victory!" in data["roundEndText"],
            )
        ):
            winning_faction = "unmc"
            winning_score = 1
        elif any(
            (
                ("Mutual Annihilation!" in data["roundEndText"]),
                ("No outcome!" in data["roundEndText"]),
            ),
        ):
            winning_faction = "none"
            winning_score = 0
        else:
            # There are all kinds of random weird end round messages now.
            # So we are going to just assume base ones don't change.
            # We mark these as UNMC with 0 score, should be good enough.
            winning_faction = "unmc"
            winning_score = 0
            # raise RuntimeError(
            #     f"Unable to parse end round message, winner unknown: {data['roundEndText']}"
            # )

        round_id = int(data["roundId"])

        return {
            "date": date,
            "map": map_str,
            "round_id": round_id,
            "winning_faction": winning_faction,
            "winning_score": winning_score,
            "players": players,
            "summary_message": data["roundEndText"],
        }

    def _load(self, transform_output: TransformOutput):
        with models.Session.begin() as session:
            map_ = (
                session.query(models.Map)
                .filter(models.Map.name == transform_output["map"])
                .one_or_none()
            )
            if not map_:
                map_ = models.Map(name=transform_output["map"])
                session.add(map_)

            if (
                session.query(models.Round)
                .filter(models.Round.id == transform_output["round_id"])
                .one_or_none()
            ):
                return

            round_ = session.merge(
                models.Round(
                    id=transform_output["round_id"],
                    map_id=map_.id,
                    winning_faction_id=(
                        session.query(models.Faction)
                        .filter(
                            models.Faction.name == transform_output["winning_faction"]
                        )
                        .one()
                        .id
                    ),
                    winning_score=transform_output["winning_score"],
                    summary_message=transform_output["summary_message"],
                    created_at=transform_output["date"],
                )
            )

            for raw_player in transform_output["players"]:
                faction = (
                    session.query(models.Faction)
                    .filter(models.Faction.name == raw_player["faction"])
                    .one()
                )

                job = (
                    session.query(models.Job)
                    .filter(
                        models.Job.name == raw_player["job"],
                        models.Job.faction_id == faction.id,
                    )
                    .one_or_none()
                )
                if not job:
                    job = models.Job(name=raw_player["job"], faction_id=faction.id)
                session.add(job)

                player = (
                    session.query(models.Player)
                    .filter(models.Player.guid == raw_player["id"])
                    .one_or_none()
                )
                if not player:
                    player = models.Player(
                        guid=raw_player["id"],
                        name=raw_player["ooc_name"],
                    )
                    session.add(player)

                player_round = (
                    session.query(models.PlayerRound)
                    .filter(
                        models.PlayerRound.player_id == player.id,
                        models.PlayerRound.round_id == round_.id,
                    )
                    .first()
                )
                if player_round:
                    player_round.job_id = job.id
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


    def saveIntoJSONFile(self, data, filename):
        with Path(CURRENT_FILE_PARENT / "data" / filename).open("w") as f:
            json.dump(data, f, indent=4)

    def loadFromJSONFile(self, filename):
        with Path(CURRENT_FILE_PARENT / "data" / filename).open("r") as f:
            return json.load(f)

    def collectCurrentReplayLinks(self, url):

        print("Current URL=" + url)
        parser = LinkHTMLParser()
        
        response = requests.get(url, timeout=5)
        parser.feed(response.text)

        for path in parser.crawlerPaths:
            if path.startswith(".."):
                continue
            if path.endswith("/"):
                self.collectCurrentReplayLinks(url + path)
            if path.endswith(".zip"):
                self.currentReplayLinks.append(url + path)
        return


    def findNewReplayLinks(self):
        self.previousReplayLinks = self.loadFromJSONFile(PREVIOUS_REPLAY_LINKS)
        self.collectCurrentReplayLinks(ROOT_URL)
        # Get only links that are new since the last time
        # Basically a set(currentLinks) - set(previousLinks), but sets dont keep the nice list ordering,
        # not that it should matter that much
        self.newReplayLinks = [link for link in self.currentReplayLinks if link not in self.previousReplayLinks]
        print("New replay links")
        for link in self.newReplayLinks:
            print(link)
            


    def downloadFile(self, replay_url):
        zipFileName = Path(replay_url).name
        localFilePath = Path( CURRENT_FILE_PARENT / "data" / "yaml" / zipFileName).with_suffix(".yaml")

        try:
            remote_zip_file = unzip_http.RemoteZipFile(replay_url)
            yamlData = remote_zip_file.open("_replay/replay_final.yml").read()
            with localFilePath.open("wb") as f:
                f.write(yamlData)
            print(f"Downloaded {replay_url}")

        except Exception as e:
            print(e)
            print(f"Ingoring a bad zip file {replay_url}")


    # Used only in the case that you dont have the oldReplayLinks file so you are starting completely fresh
    def collectEverythingWhenNoData(self):
        self.collectCurrentReplayLinks(ROOT_URL)
        self.saveIntoJSONFile(self.currentReplayLinks, OLD_REPLAY_LINKS)

    # Given a list of links just download them all
    def downloadReplaysFromFile(self, filename):
        replayList = self.loadFromJSONFile(filename)
        for link in replayList:
            self.downloadFile(link)






    def processFromLocalFiles(self):



        # Get links when you have no previous data, and then download them
        # self.collectEverythingWhenNoData()
        # self.downloadReplaysFromFile(OLD_REPLAY_LINKS)

        # Should be ran only when triggered in CICD
        if GITHUB_ACTION == "true":
            self.findNewReplayLinks()
            for replayLink in self.newReplayLinks:
                self.downloadFile(replayLink)
            # current becomes previous
            self.saveIntoJSONFile(self.currentReplayLinks, PREVIOUS_REPLAY_LINKS)
        elif IN_DOCKER == "true":
            for extract_output in self._extractFromLocal():
                transform_output = self._transform(extract_output)
                if not transform_output:
                    continue
                self._load(transform_output)
        else:
            print("Didnt do anything")




if __name__ == "__main__":
    replays = Replays()
    
    # Default functionality that can still be triggered, I just replaced it with local file loading
    # replays.process()

    replays.processFromLocalFiles()
    print("Done")






# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/06/09/2024_06_09-17_28-round_7.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/06/09/2024_06_09-18_06-round_74.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/07/03/2024_07_03-23_06-round_209.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/07/10/2024_07_10-02_51-round_302.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/07/10/2024_07_10-22_05-round_315.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/10/27/2024_10_27-21_33-round_1746.zip
# Bad zip file https://replays.rouny-ss14.com/replays/alamo/2024/10/28/2024_10_28-20_26-round_1764.zip
