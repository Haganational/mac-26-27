# Tops and Bottoms: The Lock Call

The show bible. Matthew set all of this on Nov 23, 2026. Nothing publishes without his OK on a cut.

## The show
- Two minutes, daily, released with the picks column (the card locks 7:30 AM ET and the column goes up about 8:00).
- About 1,300 to 1,900 characters of script. Hardwood Bricks is unabashedly liberal and punches up, never down.
- Original sting only. No licensed music.

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
