# MAC 26-27

A season-long dashboard for MAC men's basketball: schedules and results, line
snapshots a few times a day, and (coming) a bottom-up rating model that flags gaps
against posted lines, plus a study of when MAC lines post and how they move.

## How it works

- **Schedule and results** come from ESPN's public site API, refreshed on every run
  into `data/schedule.json`.
- **Lines** come from [The Odds API](https://the-odds-api.com) (spreads, totals,
  moneylines across US books). Each run appends one row per game, book, market and
  outcome to `data/lines/YYYY-MM-DD.jsonl`, so the history is append-only and
  git-friendly. Three runs a day is about 270 requests a month, inside the free tier.
- **The collector runs on a GitHub Actions schedule** (`.github/workflows/collect.yml`),
  commits new data back to the repo, renders the dashboard and publishes it to
  GitHub Pages. No server needed.
- **The dashboard** is a static page built by `mac/build.py` from
  `templates/index.html`.

PickTheOdds stays the manual odds-shopping tool; nothing here touches it.

## Local use

```bash
pip install -r requirements.txt
python -m mac.collect schedule          # refresh schedule from ESPN
ODDS_API_KEY=... python -m mac.collect lines   # append a lines snapshot
python -m mac.collect site              # render site/index.html
python -m mac.collect build-db          # data/mac.sqlite for ad hoc queries
pytest -q
```

## Setup checklist

1. Repository secret `ODDS_API_KEY` (Settings > Secrets and variables > Actions).
2. GitHub Pages: Settings > Pages > Source: **GitHub Actions**.
3. Run the "Collect lines and publish dashboard" workflow once by hand to seed data.

## Layout

```
mac/config.py    teams, ids, aliases, paths
mac/espn.py      schedule fetch and parsing
mac/odds.py      Odds API snapshot and flattening
mac/analysis.py  standings, line history, matching, posting stats
mac/build.py     dashboard data + rendering
mac/db.py        SQLite export
mac/collect.py   CLI
data/            schedule.json, lines/*.jsonl (committed by the collector)
templates/       dashboard template
```
