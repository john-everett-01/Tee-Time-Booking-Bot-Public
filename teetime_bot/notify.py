# Plain SMTP email — stdlib only, no paid service, more reliable than carrier
# email-to-SMS gateways (which are undocumented and get discontinued without notice).

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import NOTIFY_EMAIL_FROM, NOTIFY_EMAIL_TO, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def send_notification(subject: str, body: str) -> None:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD and NOTIFY_EMAIL_TO):
        raise RuntimeError(
            "notification email not configured — set SMTP_HOST/SMTP_USER/SMTP_PASSWORD/NOTIFY_EMAIL_TO in .env"
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = NOTIFY_EMAIL_FROM
    msg["To"] = NOTIFY_EMAIL_TO
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
