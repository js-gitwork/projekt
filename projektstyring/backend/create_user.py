from __future__ import annotations

import argparse
import getpass

from sqlalchemy.exc import IntegrityError

from projektstyring.backend.auth import (
    get_user_by_username,
    hash_password,
    password_is_valid,
)
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.user import User


ALLOWED_ROLES = {
    "felt",
    "kontor",
    "admin",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Opret en bruger i Projektstyring.",
    )

    parser.add_argument(
        "username",
        help="Brugernavn",
    )

    parser.add_argument(
        "display_name",
        help="Navn som vises i systemet",
    )

    parser.add_argument(
        "role",
        choices=sorted(ALLOWED_ROLES),
        help="Brugerrolle",
    )

    parser.add_argument(
        "--must-change-password",
        action="store_true",
        help="Brugeren skal ændre password ved første login.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    username = args.username.strip().lower()
    display_name = args.display_name.strip()
    role = args.role.strip().lower()

    if not username:
        raise SystemExit("Brugernavn må ikke være tomt.")

    if not display_name:
        raise SystemExit("Navn må ikke være tomt.")

    with SessionLocal() as session:
        existing_user = get_user_by_username(
            session,
            username,
        )

        if existing_user is not None:
            raise SystemExit(
                f"Brugeren '{username}' findes allerede."
            )

        password = getpass.getpass(
            "Adgangskode: "
        )

        password_repeat = getpass.getpass(
            "Gentag adgangskode: "
        )

        if password != password_repeat:
            raise SystemExit(
                "Adgangskoderne er ikke ens."
            )

        valid, message = password_is_valid(
            password,
            role,
        )

        if not valid:
            raise SystemExit(message)

        user = User(
            username=username,
            display_name=display_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
            must_change_password=(
                args.must_change_password
            ),
        )

        session.add(user)

        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise SystemExit(
                "Brugeren kunne ikke oprettes. "
                "Kontroller om brugernavnet allerede findes."
            ) from exc

        print(
            f"Oprettet: {username} "
            f"({display_name}) - rolle: {role}"
        )


if __name__ == "__main__":
    main()
