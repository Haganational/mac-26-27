from mac import lockclip


def test_picks_newest_regular_episode_and_wraps_evenly():
    ep = lockclip.episode()
    assert not ep.get("bonus") and ep["audio"].endswith(".mp3")
    lines = lockclip.balanced("Thanksgiving gas is $3.56, Merv grades the president's under-two-dollars ticket, "
                              "and Brett and Edwin take opposite sides in San Antonio.", 46)
    assert len(lines) == 4 and all(len(ln) <= 46 for ln in lines) and len(lines[-1].split()) > 1


def test_description_leads_with_blurb_and_carries_disclosures():
    d = lockclip.description({"title": "The Lock Call: Thursday, November 26", "blurb": "Gas is $3.56."})
    assert d.startswith("Gas is $3.56.") and "1-800-GAMBLER" in d and "fictional AI" in d and "tops.html" in d


def test_clip_fits_a_short_with_the_outro():
    from mac import outro
    from datetime import date
    end = outro.for_day(date(2026, 11, 26))
    assert 45 < lockclip.clip_seconds(end) + outro.seconds(end) <= 59
