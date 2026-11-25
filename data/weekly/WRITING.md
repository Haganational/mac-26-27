# Writing a BricksIt Weekly issue

BricksIt Weekly comes out once a week per conference, four conferences a morning (three on
Sunday). The rotation is `ROTATION` in `mac/weekly.py`; `python -m mac.weekly due` prints
today's conferences (Eastern date).

## Steps, per conference

1. `LEAGUE=<key> python -m mac.weekly_brief > /tmp/brief-<key>.json` builds the facts sheet:
   standings, model ratings, this week's and last week's power ranks, every result from the
   last 7 days (score, closing spread, who covered, top scorers), the next 7 days (line,
   model margin), The Big Mid's picks (upset, player of the week, circle-it game) and news
   headlines with links.
2. Write `data/weekly/<key>/<NNN>.json`, where NNN is the brief's `next_edition_number`
   padded to three digits. Date it today (Eastern), `YYYY-MM-DD`. Copy the shape of the
   previous issue in the same folder.
3. `python -m mac.weekly check <key> data/weekly/<key>/<NNN>.json` must print `ok`.

## What goes in it

- **lead**: `kicker` (2 to 5 words), `headline`, `deck` (one or two sentences), `body` of
  4 or 5 paragraphs. The week's real story in this conference: who moved, who got exposed,
  what the schedule says that the standings don't. Lead with the result, then the why.
- **column**: `{"label": "By the Numbers" or "Look Ahead", "title", "byline": "Hardwood Bricks staff", "body": [...]}`.
  Alternate the label week to week. Look Ahead calls the next week's best games against the
  line and the model; By the Numbers is three numbers with a short paragraph each.
  Never put Matthew's name on a byline. If a Fieldhouse Notes dispatch about this conference
  was published in the last 7 days (`notes/dispatches/`), you may set
  `{"dispatch": "<slug>", "label": "The Column"}` instead; never write or edit a dispatch.
- **notes**: 4 items, `{"headline", "body"}`, one to three sentences each. The last one is
  always "Circle it:" the best game of the coming week, with day, time ET, line and TV if known.
- `"label": ""` unless the issue is special (for example "Conference tip-off edition").

## Rules

- Every score, record, spread, rank and stat comes from the brief. If a news headline
  carries the story (an injury, a coaching change), name the outlet in the text. Nothing from
  memory, nothing invented. When the brief doesn't have it, leave it out.
- Private people are never the joke. Players are college kids: praise freely, criticize the
  play, not the person.
- Voice: thorough, classy and saucy. A Sunday sports page with a wink. Short sentences,
  plain words, real verbs. No hedging, no "only time will tell", no exclamation points.
- `**bold**` and `*italic*` are the only markup.
- Spreads: say who was favored and by how much ("Dayton, favored by 6.5, won by 2 and
  didn't cover"). The model's numbers are "our model", ratings are "per 100 possessions".
