# Tops and Bottoms: The Lock Call

The show bible. Matthew set all of this on Nov 23, 2026. Nothing publishes without his OK on a cut.

## The show
- Two minutes, daily, released with the picks column (the card locks 7:30 AM ET and the column goes up about 8:00).
- About 1,300 to 1,900 characters of script. Hardwood Bricks is unabashedly liberal and punches up, never down.
- Original bumper music only. No licensed music.

## Format, in order
1. **Open.** Hello, then loose cross chatter around one news item that can be made light of.
2. **Today's picks.** All eight, each capper reading their own two.
3. **The board.** Who is on top overall, and who was on top yesterday.
4. **Close.** Closing chatter, the column plug, the 21+ / 1-800-GAMBLER line, "Keep it mid. Keep it real."

## The cast
- **Leslie Phyllis** (main host). Tunica's own. A new-wave progressive in the AOC and Mamdani mold: tax the rich, organize, joy as a weapon. Warm, quick, calls people "honey".
- **Brett Busberger** (main host). Mr. JuiceBox. A Clinton and Obama institutionalist: trusts the model, the process and a good spreadsheet. Sunny and hydrated.
- **Merv Crutch.** Hall of Famer. More moderate, but a lifelong civil rights Democrat. Dry, brief, the moral weight in the room. Loves an under.
- **Edwin "The Shark" Sinclair.** Atlantic City. The MAGA reactionary, sweating and out of breath, and always put in his place by the other three inside a line or two. He never wins an argument and never gets the last word on politics. His "inside information" stays invented people only.

## The news item
- Searched twice each morning, about 3 AM and 6 AM ET. One item is picked; show notes carry it with source links.
- Fair game: the president, his administration and inner circle as public figures (Trump, Vance, Rubio, Miller, Hegseth, Lutnick, Bessent, Kushner, Ivanka Trump and the rest), fascist organizations, and billionaires' public conduct.
- Never: private people, players, coaches, students, fans.
- Every factual claim comes from a page that was actually opened. Quotes are verbatim or not used. Jokes are opinion and exaggeration about public conduct, never an invented fact or an invented quote.
- Skip tragedy. If the only news is grim, the open is basketball chatter instead.

## The numbers
- Every pick, record, unit and score comes from `python -m mac.lockcall facts`. Nothing is rounded into a different claim.
- Picks are entertainment, never advice.

## Making an episode
1. `python -m mac.lockcall facts` for the day's card.
2. Write `data/podcast/YYYY-MM-DD.json`: `lines` (part, who, text) and `notes` (news item with sources).
3. `python -m mac.lockcall check` then `render`. Run speech-to-text on the result and compare to the script.
4. Matthew hears the cut before anything posts.

## The hook rule (Matthew, Nov 23: "the most creative upbeat hooks, for immediate retention, as a guiding light")
- The first thing heard is the hook: the day's best line, cold, before any music or hello. One or two short lines, 170 characters at most, upbeat, and it must pay off inside the episode.
- Good hooks: a true, startling line from the news item; a number that sounds impossible (a 40-point underdog, a half-point loss); a tease of someone about to be embarrassed, usually Edwin; a promise with a clock on it ("Eight picks, two minutes").
- Never a greeting, never the show's name, never "welcome back". The name comes after the bumper.
- Order of an episode: hook, bumper in, open, picks, board, close, bumper out.

## Music
- One original bumper theme (data/podcast/theme.mp3, made for the show Nov 23, 2026). It hits on the hook's last word, plays alone for a few seconds, ducks under the hello, and comes back under the goodbye to end on its button.

## Daily run (Matthew, Nov 23 2026: "Auto publish the pod")

The show publishes on its own every morning; no review step. Times are Eastern.

1. About 3 AM and 6 AM: search the news, verify the chosen item by opening the page, write show notes.
2. After the 7:30 lock (about 8:05): `python -m mac.lockcall facts`, write `data/podcast/DATE.json` with `title` ("The Lock Call: Weekday, Month D") and a one-sentence `blurb`, then `check`, `render`, and a speech-to-text pass on the raw renders to confirm every pick, number and record.
3. `python -m mac.lockcall publish data/podcast/DATE.json OUT.mp3` copies the audio into the site and adds the row to `episodes.json`. Merge to main. The site and feed pick it up on the next build, and the "lock call" workflow posts it to Bluesky.

Hold the episode and tell Matthew instead of publishing if: there is no card for the day, the speech-to-text pass shows a wrong pick or number that a re-record does not fix, or no news item can be verified (then run without a news bit rather than guess).
