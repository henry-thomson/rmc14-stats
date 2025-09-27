Continuation of https://github.com/diraven/rmc14-stats

Open an issue if you are not sure how to start project, or have any questions.

## How to use
Assuming everything works as expected, you should only need to have a docker and docker compose installed.
- https://docs.docker.com/get-started/get-docker/
- https://docs.docker.com/compose/install/

You should be good if you can run
```
docker --version
docker compose --version
```

You can then load the data from the DB data dump(needs to be done only once) with:
```
docker compose -f docker-compose-initial.yml up
```
If you see `database system is ready to accept connections` in the logs, everything should have finished and you can stop the project with `ctrl+C`.

You can then start the whole project with:
```
docker compose up --force-recreate --build
```
It would start a local DB, Grafana with the same graphs that previous project used, and load the most recent data. Then you can visit http://localhost:3000/, use `admin` username and password, and browse whatever you want.

## Changes
### Old
I believe that the previous project had a remote server that had a DB where all of the data was saved. Every two hours a github workflow would collect new data, and add it into the DB. You can still use the old project, start your own DB, and it will load the data into the DB. However, it is missing a Grafana instance, dashboards, and I personally had issues with the DB migrations.

### Current
- Added dashboards that the old project used, and a Grafana instance.
- Contains ALL data from RMC 14 replays. Not sure if it is useful, and some of the dashboards still use only the last 30 days, but it is there, and anyone can access it without having to scrape the replays again.
- Unless someone hosts this project, the main way of viewing the statistics would be through running it yourself locally. This also means if you have any new dashboards you would like for others to see, you can create a pull request and they can be easily added.

## Extra notes
I am not sure what happened to the previous project, but I wanted to keep it alive, and make it as simple as possible for anyone interested to build on top of what was created before.
However, while trying to keep all of the previous code unchanged, the current state of the code is in a bit of a disarray. So just a warning that it might be a bit confusing.
I am very much aware of how awful the code, instructions, and everything that has been commited to the git is. My prime goal was to allow anyone who can install docker to run the project. There are certainly better ways to achieve the same, I just didn't want to make 50 step README, and I didn't want to spend too much time on the project. Any suggestions and improvements are extremely welcome.
