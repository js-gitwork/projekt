
from __future__ import annotations

import os
from urllib.parse import quote

import httpx


GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphMailError(RuntimeError):
    """Fejl ved autentificering eller mailafsendelse."""


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()

    if not value:
        raise GraphMailError(
            f"Miljøvariablen {name} mangler."
        )

    return value


def send_mail(
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    """
    Sender en tekstmail gennem Microsoft Graph.

    Funktionen kræver en Entra-app med Mail.Send
    Application permission og adgang til afsenderen.
    """

    if not recipients:
        raise GraphMailError(
            "Der er ingen modtagere."
        )

    tenant_id = _required_environment(
        "VPMANHOLE_GRAPH_TENANT_ID"
    )
    client_id = _required_environment(
        "VPMANHOLE_GRAPH_CLIENT_ID"
    )
    client_secret = _required_environment(
        "VPMANHOLE_GRAPH_CLIENT_SECRET"
    )
    sender = _required_environment(
        "VPMANHOLE_GRAPH_SENDER"
    )

    token_url = (
        f"https://login.microsoftonline.com/"
        f"{quote(tenant_id, safe='')}/oauth2/v2.0/token"
    )

    with httpx.Client(timeout=30.0) as client:
        try:
            token_response = client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": GRAPH_SCOPE,
                    "grant_type": "client_credentials",
                },
            )
            token_response.raise_for_status()

            access_token = token_response.json()[
                "access_token"
            ]

        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
        ) as exc:
            raise GraphMailError(
                "Kunne ikke hente Microsoft Graph-token."
            ) from exc

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": address,
                        }
                    }
                    for address in recipients
                ],
            },
            "saveToSentItems": True,
        }

        url = (
            f"{GRAPH_BASE_URL}/users/"
            f"{quote(sender, safe='')}/sendMail"
        )

        try:
            response = client.post(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                },
                json=payload,
            )
            response.raise_for_status()

            if response.status_code != 202:
                raise GraphMailError(
                    "Microsoft Graph bekræftede ikke "
                    "modtagelsen af mailen."
                )

        except httpx.HTTPError as exc:
            status = (
                exc.response.status_code
                if isinstance(
                    exc,
                    httpx.HTTPStatusError,
                )
                else "ukendt"
            )

            raise GraphMailError(
                "Microsoft Graph-mailafsendelse "
                f"fejlede (HTTP {status})."
            ) from exc
