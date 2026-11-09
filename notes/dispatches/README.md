# Fieldhouse Notes

Each `.md` file in this folder is one dispatch on the site's Fieldhouse Notes page.
The easiest way to add one is the **author desk** on the site (`desk.html`): write the
dispatch, pick its icon and what it is about, see the preview, and **Save draft**. Each
draft becomes its own pull request. **Publish** merges it, and the site republishes for
everyone a few minutes later. The desk talks to GitHub with a fine-grained token that
stays in your browser only. The **+ Add dispatch** buttons around the site (author mode)
open the desk with the game, team or player filled in. You can also add a file here by hand:

```
---
kind: arena   # phone, paper, tv or arena (in person): the icon it is filed with
game: 401812345   # ESPN game id: filed with the game and both teams
team: ohio        # team key(s), comma separated: filed with the team
player: 5105569   # ESPN player id: filed with the player
title: Short headline
date: 2026-11-12
draft: true       # optional: keeps it off the site (the repo is public, so it is still visible here)
---
The dispatch, in Markdown: blank line between paragraphs, **bold**, *italic*,
[link](https://...), - lists, > quotes.
```

Only accounts with write access to this repository can commit, so only you can add
or edit dispatches. Everyone else can only read them on the site.
