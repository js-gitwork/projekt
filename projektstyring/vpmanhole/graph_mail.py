from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)


class GraphMailError(RuntimeError):
    """Fejl ved afsendelse gennem SMTP-relay."""


def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    """
    Sender mail gennem IP-godkendt Microsoft 365 SMTP-relay.

    Ingen brugernavn eller adgangskode.
    STARTTLS kræves.
    """

    if not recipients:
        raise GraphMailError("Der er ingen modtagere.")

    host = os.environ.get(
        "VPMANHOLE_SMTP_HOST", ""
    ).strip()
    sender = os.environ.get(
        "VPMANHOLE_SMTP_FROM", ""
    ).strip()

    try:
        port = int(os.environ.get("VPMANHOLE_SMTP_PORT", "25"))
    except ValueError as exc:
        raise GraphMailError("Ugyldig SMTP-port.") from exc

    if not host or not sender:
        raise GraphMailError(
            "SMTP-server eller afsenderadresse mangler."
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    message.set_content(body)

    try:
        with smtplib.SMTP(
            host=host,
            port=port,
            timeout=30,
        ) as smtp:
            smtp.ehlo()

            if not smtp.has_extn("starttls"):
                raise GraphMailError(
                    "SMTP-serveren understøtter ikke STARTTLS."
                )

            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()

            refused = smtp.send_message(
                message,
                from_addr=sender,
                to_addrs=recipients,
            )

            if refused:
                raise GraphMailError(
                    f"SMTP afviste modtagere: {refused}"
                )

    except (smtplib.SMTPException, OSError) as exc:
        raise GraphMailError(
            f"SMTP-afsendelse fejlede: {exc}"
        ) from exc

    logger.info(
        "SMTP-relay accepterede mail til %s modtager(e).",
        len(recipients),
    )