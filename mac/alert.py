"""Email Matthew when something needs a person: a skipped video, social posts that keep failing.

Sends through Gmail's SMTP with an app password. Needs two repo secrets, set by the account
owner: ALERT_SMTP_USER (the Workspace mailbox, e.g. matthew@hardwoodbricks.com) and
ALERT_SMTP_PASSWORD (a Google app password, never the account password). ALERT_TO is optional
and defaults to desk@hardwoodbricks.com. Without the secrets the alert is printed as a GitHub
Actions warning instead, so it still shows on the run page. Sending never raises.
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

DEFAULT_TO = "desk@hardwoodbricks.com"
HOST, PORT = "smtp.gmail.com", 465


def message(subject: str, body: str, sender: str, to: str) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = f"[Hardwood Bricks] {subject}"
    m["From"] = sender
    m["To"] = to
    m.set_content(body.rstrip() + "\n")
    return m


def send(subject: str, body: str) -> bool:
    """True when the email went out. Always prints a warning line for the run log."""
    print(f"::warning::{subject}: {' '.join(body.split())[:400]}")
    user = os.environ.get("ALERT_SMTP_USER", "").strip()
    password = "".join(os.environ.get("ALERT_SMTP_PASSWORD", "").split())  # app passwords paste with spaces
    to = os.environ.get("ALERT_TO", "").strip() or DEFAULT_TO
    if not (user and password):
        print("alert: no ALERT_SMTP_* secrets set, email not sent")
        return False
    try:
        with smtplib.SMTP_SSL(HOST, PORT, timeout=30) as s:
            s.login(user, password)
            s.send_message(message(subject, body, user, to))
    except (OSError, smtplib.SMTPException) as exc:
        print(f"alert: email failed ({type(exc).__name__}: {exc})")
        return False
    return True
