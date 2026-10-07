import hmac
import secrets

from fastapi import Form, HTTPException, Request


CSRF_SESSION_KEY = "csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

UNSAFE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


def get_csrf_token(request: Request) -> str:
    """
    Returnerer sessionens CSRF-token.

    Hvis sessionen endnu ikke har et token, oprettes et
    kryptografisk tilfældigt token og gemmes i sessionen.
    """
    token = request.session.get(CSRF_SESSION_KEY)

    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token

    return token


def csrf_tokens_match(
    expected_token: str | None,
    supplied_token: str | None,
) -> bool:
    """
    Sammenligner CSRF-tokens med konstant-tids sammenligning.
    """
    if not expected_token or not supplied_token:
        return False

    return hmac.compare_digest(
        expected_token,
        supplied_token,
    )


def validate_csrf_token(
    request: Request,
    csrf_token: str = Form(...),
) -> None:
    """
    Validerer CSRF-token fra en almindelig HTML-formular.

    FastAPI står selv for parsing af formularen, så vi undgår
    at middleware forbruger request-bodyen.
    """
    expected_token = request.session.get(CSRF_SESSION_KEY)

    if not csrf_tokens_match(
        expected_token,
        csrf_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="Ugyldigt eller manglende CSRF-token.",
        )


def csrf_header_is_valid(request: Request) -> bool:
    """
    Validerer CSRF-token fra X-CSRF-Token-headeren.

    Denne funktion læser aldrig request-bodyen og kan derfor
    bruges sikkert før FastAPI behandler requesten.
    """
    expected_token = request.session.get(CSRF_SESSION_KEY)
    supplied_token = request.headers.get(CSRF_HEADER)

    return csrf_tokens_match(
        expected_token,
        supplied_token,
    )
