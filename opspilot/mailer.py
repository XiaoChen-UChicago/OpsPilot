from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Iterable

import requests


class MailSendError(RuntimeError):
    pass


def send_microsoft_mail(access_token: str, recipient: str, subject: str, body: str) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
        },
        "saveToSentItems": True,
    }
    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=25,
    )
    if response.status_code >= 300:
        raise MailSendError(f"Microsoft Graph returned HTTP {response.status_code}.")


def send_google_mail(access_token: str, recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
    response = requests.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": encoded},
        timeout=25,
    )
    if response.status_code >= 300:
        raise MailSendError(f"Gmail API returned HTTP {response.status_code}.")


def send_batch(provider: str, access_token: str, messages: Iterable[dict[str, str]], max_messages: int = 20) -> int:
    """Send a small, explicitly approved batch and stop on the first provider error."""
    queued = list(messages)
    if not queued:
        return 0
    if len(queued) > max_messages:
        raise MailSendError(f"A single approval can send at most {max_messages} messages.")
    sender = send_microsoft_mail if provider == "microsoft" else send_google_mail if provider == "google" else None
    if sender is None:
        raise MailSendError(f"Unsupported mail provider: {provider}")
    for message in queued:
        sender(access_token, message["recipient"], message["subject"], message["body"])
    return len(queued)
