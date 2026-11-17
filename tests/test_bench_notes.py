from mac.gamer import bench_notes



def test_losing_bench_leads_with_its_daylight():
    us = {"stats": {"largestLead": "12", "totalRebounds": "41", "freeThrowsMade-freeThrowsAttempted": "6-9"}}
    them = {"stats": {"largestLead": "7", "totalRebounds": "30", "freeThrowsMade-freeThrowsAttempted": "18-24"}}
    notes = bench_notes(us, them, "Ohio", "Akron", False, 6.5, 3)
    assert len(notes) == 2
    assert notes[0].endswith("a cover.")
    assert all("Ohio" in t for t in notes)


def test_no_daylight_no_notes():
    us = {"stats": {"largestLead": "2", "totalRebounds": "33", "freeThrowsMade-freeThrowsAttempted": "10-14"}}
    them = {"stats": {"largestLead": "15", "totalRebounds": "35", "freeThrowsMade-freeThrowsAttempted": "12-16"}}
    assert bench_notes(us, them, "Ohio", "Akron", False, -4.0, 14) == []


def test_winner_wire_to_wire_and_skips_repeats():
    us = {"stats": {"largestLead": "20"}}
    them = {"stats": {"largestLead": "0"}}
    assert bench_notes(us, them, "Kent State", "Toledo", True, None, 18) == ["Kent State never trailed."]
    assert bench_notes(us, them, "Kent State", "Toledo", True, None, 18, already="Kent State never trailed.") == []
