from mac import honors


def test_ohio_film_is_pinned():
    f = honors.films()
    assert f["ohio"][0]["youtube"] == "H6GUKT38RN0" and f["ohio"][0]["title"]


def test_line_reads_like_a_box_score():
    r = {"pts": 31, "reb": 9, "ast": 2}
    assert honors._line(r) == "31 points, 9 rebounds"
