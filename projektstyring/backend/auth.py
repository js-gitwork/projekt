from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from projektstyring.backend.db_models.user import User


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Opretter en sikker Argon2-hash af et password.
    """
    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    """
    Kontrollerer et password mod den gemte hash.
    """
    return password_hash.verify(
        password,
        hashed_password,
    )


def password_is_valid(
    password: str,
    role: str,
) -> tuple[bool, str]:
    """
    Fælles regler for adgangskoder.

    Felt- og kontorbrugere:
    mindst 4 tegn.

    Administrator:
    mindst 8 tegn.
    """
    if role in {"felt", "kontor"}:
        if len(password) < 4:
            return (
                False,
                "Adgangskoden skal være mindst 4 tegn.",
            )

        return True, ""

    if role == "admin":
        if len(password) < 8:
            return (
                False,
                "Admin-adgangskoden skal være mindst 8 tegn.",
            )

        return True, ""

    return False, "Ukendt brugerrolle."


def get_user_by_username(
    session: Session,
    username: str,
) -> User | None:
    """
    Finder en bruger ud fra brugernavn.
    """
    normalized_username = username.strip().lower()

    if not normalized_username:
        return None

    statement = select(User).where(
        User.username == normalized_username,
    )

    return session.scalar(statement)


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> User | None:
    """
    Validerer brugernavn og adgangskode.

    Returnerer kun aktive brugere.
    """
    user = get_user_by_username(
        session,
        username,
    )

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user