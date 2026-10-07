from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from projektstyring.backend.csrf import (
    CSRF_HEADER,
    CSRF_SESSION_KEY,
    csrf_header_is_valid,
    csrf_tokens_match,
    get_csrf_token,
    validate_csrf_token,
)


def test_csrf_tokens_match():
    assert csrf_tokens_match("abc123", "abc123") is True
    assert csrf_tokens_match("abc123", "wrong") is False
    assert csrf_tokens_match("abc123", None) is False
    assert csrf_tokens_match(None, "abc123") is False


def test_get_csrf_token_reuses_existing_session_token():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "existing-token",
    }

    token = get_csrf_token(request)

    assert token == "existing-token"
    assert request.session[CSRF_SESSION_KEY] == "existing-token"


def test_get_csrf_token_creates_missing_session_token():
    request = MagicMock()
    request.session = {}

    token = get_csrf_token(request)

    assert isinstance(token, str)
    assert token
    assert request.session[CSRF_SESSION_KEY] == token


def test_valid_form_token_is_accepted():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }

    result = validate_csrf_token(
        request,
        csrf_token="correct-token",
    )

    assert result is None


def test_wrong_form_token_is_rejected():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }

    with pytest.raises(HTTPException) as exc_info:
        validate_csrf_token(
            request,
            csrf_token="wrong-token",
        )

    assert exc_info.value.status_code == 403


def test_missing_form_token_is_rejected():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }

    with pytest.raises(HTTPException) as exc_info:
        validate_csrf_token(
            request,
            csrf_token="",
        )

    assert exc_info.value.status_code == 403


def test_valid_header_token_is_accepted():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }
    request.headers = {
        CSRF_HEADER: "correct-token",
    }

    assert csrf_header_is_valid(request) is True


def test_wrong_header_token_is_rejected():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }
    request.headers = {
        CSRF_HEADER: "wrong-token",
    }

    assert csrf_header_is_valid(request) is False


def test_missing_header_token_is_rejected():
    request = MagicMock()
    request.session = {
        CSRF_SESSION_KEY: "correct-token",
    }
    request.headers = {}

    assert csrf_header_is_valid(request) is False
