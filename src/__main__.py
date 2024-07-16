import collections
import csv
import enum
import pathlib
import re
import typing as t

import requests
import unzip_http
import yaml
from loguru import logger

ROOT_URL = "https://replays.rouny-ss14.com/replays/alamo"
HREF_FINDER = re.compile(r'<a href="([\d]+)\/">')
REPLAY_FINDER = re.compile(r'<a href="([^"]+\.zip)">')


@enum.unique
class Win(enum.IntEnum):
    MARINE = 0
    XENO = 1
    # DRAW = 2


class Cache(t.TypedDict):
    last_checked: float
    entries: t.Dict[str, str]


class Replays:
    _cache: Cache

    @property
    def _replay_urls(self):
        response = requests.get(ROOT_URL)
        for year in HREF_FINDER.finditer(response.text):
            year = year.group(1)
            response = requests.get(f"{ROOT_URL}/{year}/")
            for month in HREF_FINDER.finditer(response.text):
                month = month.group(1)
                response = requests.get(f"{ROOT_URL}/{year}/{month}/")
                for day in HREF_FINDER.finditer(response.text):
                    day = day.group(1)
                    response = requests.get(f"{ROOT_URL}/{year}/{month}/{day}/")
                    for replay in REPLAY_FINDER.finditer(response.text):
                        replay = replay.group(1)
                        replay_url = f"{ROOT_URL}/{year}/{month}/{day}/{replay}"
                        yield replay_url

    def refresh(self):
        for replay_url in self._replay_urls:
            filename = replay_url.split("/")[-1].replace(".zip", ".yml")
            if (pathlib.Path(".cache") / filename).exists():
                continue
            try:
                logger.info(f"Downloading {replay_url}")
                remote_zip_file = unzip_http.RemoteZipFile(replay_url)

                data = yaml.safe_load(
                    remote_zip_file.open_text("_replay/replay_final.yml").read()  # type: ignore
                )
                data = self._sanitize_data(data)

                with open(f".cache/{filename}", "w") as replay_file:
                    replay_file.write(yaml.dump(data))
            except Exception:
                logger.warning(f"Bad zip file {replay_url}")
                # Just save empty files so that we don't try to download them again.
                with open(f".cache/{filename}", "w") as replay_file:
                    replay_file.write("")

    def _sanitize_data(self, summary: dict[str, str]) -> dict[str, str]:
        try:
            del summary["roundEndPlayers"]
        except KeyError:
            pass

        return summary

    def _parse_summaries(self):
        for replay_path in (pathlib.Path(".cache")).glob("*.yml"):
            with open(replay_path) as replay:
                summary = yaml.safe_load(replay)
            if summary is None:  # sometimes summary files are empty
                continue
            if (
                summary["roundEndText"] is None
            ):  # sometimes end of round summary is empty
                continue

            date = replay_path.name.split("-")[0]

            map = None
            try:
                map = summary["maps"][1]
            except (KeyError, TypeError):
                map = summary["map"]
            if map == "Solaris":
                map = "Solaris Ridge"

            if any(
                (
                    "All of the xenos were wiped out!" in summary["roundEndText"],
                    "Marine Major victory!" in summary["roundEndText"],
                    "The xenos hijacked a dropship" in summary["roundEndText"]
                    and "but were wiped out by the marine" in summary["roundEndText"],
                ),
            ):
                win = Win.MARINE
            elif any(
                ("All of the marines were wiped out!" in summary["roundEndText"],)
            ):
                win = Win.XENO
            elif any(
                (("Mutual Annihilation!" in summary["roundEndText"]),),
            ):
                continue
                # win = Win.DRAW
            else:
                raise RuntimeError(
                    f"Unable to parse end round message, winner unknown: {summary['roundEndText']}"
                )

            yield date, map, win

    def count(self):
        return collections.Counter(self._parse_summaries())


replays = Replays()
replays.refresh()
counter = replays.count()


results = collections.defaultdict(
    lambda: collections.defaultdict(lambda: collections.defaultdict(int))
)
for key in sorted(counter):
    if key[2] == Win.XENO:
        results[key[0]][key[1]]["Xeno"] += counter[key]
    if key[2] == Win.MARINE:
        results[key[0]][key[1]]["Marine"] += counter[key]
    # if key[2] == Win.DRAW:
    #     results[key[0]][key[1]]["Draw"] += counter[key]

# Dump results into csv.
with open(".results.csv", "w", newline="") as csv_file:
    csv_writer = csv.writer(csv_file)
    # csv_writer.writerow(["Date", "Map", "Marine", "Draw", "Xeno"])
    csv_writer.writerow(["Date", "Map", "Marine", "Xeno"])
    for map in results:
        for date in results[map]:
            csv_writer.writerow(
                [
                    map,
                    date,
                    results[map][date]["Marine"],
                    results[map][date]["Xeno"],
                ]
            )
