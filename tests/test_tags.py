from mac import cards, leagues, tags, youtube, reels


def pair(short):
    return next((t, lg) for lg in leagues.ALL.values() for t in lg.teams if t.short == short)


def test_clean_handles_accents_and_punctuation():
    assert tags.clean("San José St") == "#SanJoseSt"
    assert tags.clean("Hawai'i") == "#Hawaii"
    assert tags.clean("Texas A&M-CC") == "#TexasAMCC"


def test_specific_alternates_school_and_conference_without_repeats():
    got = tags.specific([pair("Kent State"), pair("Akron"), pair("Drake")])
    assert got == ["#KentState", "#MACtion", "#Akron"]


def test_line_never_passes_five():
    assert tags.line(["#A", "#B", "#C", "#D"]).split() == ["#Midmaxxing", "#CollegeBasketball", "#A", "#B", "#C"]


def test_youtube_shows_school_first_and_adds_search_words():
    b = youtube.body("midmaxx60-2026-11-15", "x", "public", ["#KentState", "#MACtion", "#Drake"])
    assert b["snippet"]["description"].endswith("#Shorts #KentState #MACtion #Midmaxxing #CollegeBasketball")
    assert "Kent State" in b["snippet"]["tags"]


def test_reel_captions_carry_the_day_tags():
    assert "#KentState" in reels.caption("midmaxx60-2026-11-15", "lead", "midmaxx60", specific=["#KentState"])
    assert len(reels.short_caption("midmaxx60-2026-11-15", "midmaxx60", ["#KentState", "#MACtion"])) <= 300


def test_card_tags_keep_first_line_and_disclosure_last():
    caps = {"instagram": f"Head\n\nBody\n\n{cards.DISCLOSURE}", "threads": "Head", "bluesky": "x" * 299}
    out = cards.tag_caps(caps, ["#KentState"])
    assert out["instagram"].startswith("Head") and out["instagram"].endswith(cards.DISCLOSURE)
    assert "#KentState" in out["instagram"] and out["threads"] == "Head\n\n#KentState"
    assert out["bluesky"] == "x" * 299  # would not fit, left alone
