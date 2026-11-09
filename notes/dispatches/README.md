# Fieldhouse Notes

Each `.md` file in this folder is one dispatch on the site's Fieldhouse Notes page.
The easiest way to add one is the **+ Add dispatch** button on the site, in author mode
(open `notes.html?author=1` once on your phone or laptop). It opens GitHub's editor with
this template filled in. Commit to `main` and the site republishes in a few minutes.

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
