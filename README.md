# MAC 26-27

A season-long dashboard for MAC men's basketball: schedules and results, line
snapshots a few times a day, a bottom-up rating model that flags gaps against
posted lines, and (coming) a study of when MAC lines post and how they move.

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
- **Every D-I result** comes from ESPN's scoreboard (one request per day) into
  `data/ncaa/games-<season>.json`, with turnovers, offensive rebounds and the
  DraftKings closing line added from each game's summary. The model needs the whole
  D-I graph to rate MAC opponents.
- **The rating model** (`mac/ratings.py`) solves offense, defense and pace for every
  D-I team at once by weighted least squares on points per 100 possessions:
  opponent- and venue-adjusted, recency-weighted (half-life 90 days), blowouts
  damped, starting from last season's ratings regressed 20% to average. It projects
  spread, total and win probability for each MAC game, compares them with the
  market, and logs each run to `data/model/projections.jsonl`. The ratings page is
  `site/ratings.html`.
- **The backtest** (`python -m mac.backtest`) replays 2025-26 one morning at a time
  with only earlier games and scores the model against results and DraftKings
  closing lines; `python -m mac.backtest tune` sweeps the knobs.
- **CollegeBasketballData.com** (`mac/cbbd.py`, `mac/cbbd_study.py`) supplies box scores
  back to 2003 and opening + closing lines back to 2013 for a multi-season backtest
  (Actions > "CollegeBasketballData backfill and study", needs the `CBBD_API_KEY` secret;
  free tier is 1,000 calls a month and a season costs about 15). Their terms forbid a
  public mirror, so raw responses stay in a private Actions cache (`data/cache/`, git-ignored)
  and only summary numbers are committed. Data provided by CollegeBasketballData.com.
- **The dashboard** is a static page built by `mac/build.py` from
  `templates/index.html`.

- **The odds screen** (`odds.html`, built by `mac/oddsboard.py`) shows every book's
  spread, total and moneyline for each MAC game on the board, with the best price on
  each side, each book's open vs current number, hold, off-market flags, the
  consensus path, which book posted first, a book scorecard and the API budget. It
  is built from the saved snapshots, so it costs no extra requests. Once the rating
  model writes `data/model/projections.jsonl`, model-vs-market gaps appear there too.
- **Books** are named in `ODDS_BOOKMAKERS` in `mac/config.py`. The API bills every 10
  named books (from any region) as one region, so the current 10 (DraftKings,
  FanDuel, BetMGM, theScore Bet, Novig, Pinnacle, BetRivers, Hard Rock, BetOnline,
  Bovada) cost the same 3 requests a run as `regions=us`. BetJACK is not offered by
  The Odds API; Caesars and Fanatics need a paid plan. Each run's quota counters are
  logged to `data/odds_runs.jsonl`.

## Local use

```bash
pip install -r requirements.txt
python -m mac.collect schedule          # refresh schedule from ESPN
ODDS_API_KEY=... python -m mac.collect lines   # append a lines snapshot
python -m mac.collect ncaa              # refresh this season's D-I results
python -m mac.collect ncaa-backfill     # one-time: two prior seasons (~12k summary requests)
python -m mac.collect ratings           # print MAC ratings
python -m mac.backtest                  # walk-forward backtest, writes data/model/backtest.json
python -m mac.collect site              # render site/index.html
python -m mac.collect build-db          # data/mac.sqlite for ad hoc queries
pytest -q
```

## Setup checklist

1. Repository secret `ODDS_API_KEY` (Settings > Secrets and variables > Actions).
   Optional: `CBBD_API_KEY` for the CollegeBasketballData.com study.
2. GitHub Pages: Settings > Pages > Source: **GitHub Actions**.
3. Run the "Collect lines and publish dashboard" workflow once by hand to seed data.
4. Optional repo variables (Settings > Secrets and variables > Actions > Variables):
   `SITE_URL` when the site moves to a custom domain (share cards and canonical links
   use it), `SITE_NOINDEX=1` to ask search engines not to index the site.

## Navigation, colors and sharing

- Every page imports `templates/_layout.html` for the head (Open Graph / X card tags),
  the sticky top bar (pages, a Teams menu, search, share) and the footer.
- `templates/static/nav.js` runs search (`/` or Ctrl+K) over `site/search.json`,
  builds the "On this page" bar, adds a copy-link `#` to every section heading and
  opens the share menu (native share sheet on phones).
- `mac/site_chrome.py` runs after rendering: gives every `<section>` with an `<h2>` a
  stable id, writes the search index (pages, sections, teams, coaches, players, every
  game), `static/teams.css` from the colors in `mac/config.py` (`.t-<key>` sets
  `--tc`, `--tc2`, `--tci`), 1200x630 share cards in `static/og/` (site, each page,
  each team, each final), app icons, `manifest.webmanifest`, `robots.txt`, `sitemap.xml`.

## Layout

```
mac/config.py    teams, ids, aliases, paths
mac/espn.py      schedule fetch and parsing
mac/odds.py      Odds API snapshot and flattening
mac/analysis.py  standings, line history, matching, posting stats
mac/ncaa.py      every D-I result from ESPN's scoreboard + summary extras
mac/ratings.py   the rating model: fit, project, team table, walk-forward
mac/model.py     current ratings, MAC projections vs market, run logs
mac/backtest.py  walk-forward backtest and knob sweep
mac/build.py     dashboard data + rendering
mac/site_chrome.py  search index, section anchors, team colors, share cards
mac/db.py        SQLite export
mac/collect.py   CLI
data/            schedule.json, lines/*.jsonl (committed by the collector)
templates/       dashboard template
```
