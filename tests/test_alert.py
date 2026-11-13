from mac import alert


def test_without_secrets_it_warns_and_sends_nothing(monkeypatch, capsys):
    monkeypatch.delenv("ALERT_SMTP_USER", raising=False)
    monkeypatch.delenv("ALERT_SMTP_PASSWORD", raising=False)
    assert alert.send("MAC90 skipped", "the data\nwas old") is False
    assert "::warning::MAC90 skipped: the data was old" in capsys.readouterr().out


def test_sends_to_the_desk_alias_by_default(monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, host, port, timeout):
            seen["host"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            seen["login"] = (user, password)

        def send_message(self, m):
            seen["msg"] = m

    monkeypatch.setattr(alert.smtplib, "SMTP_SSL", Fake)
    monkeypatch.setenv("ALERT_SMTP_USER", "matthew@hardwoodbricks.com")
    monkeypatch.setenv("ALERT_SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.delenv("ALERT_TO", raising=False)
    assert alert.send("Social posts to bluesky keep failing", "body") is True
    assert seen["login"] == ("matthew@hardwoodbricks.com", "abcdefghijklmnop")
    assert seen["msg"]["To"] == "desk@hardwoodbricks.com" and seen["msg"]["Subject"].startswith("[Hardwood Bricks] ")
