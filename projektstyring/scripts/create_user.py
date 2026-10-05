from __future__ import annotations

import getpass

from sqlalchemy.exc import IntegrityError

from projektstyring.backend.auth import (
    hash_password,
    password_is_valid,
)
from projektstyring.backend.database.connection import SessionLocal
from projektstyring.backend.db_models.user import User


VALID_ROLES = {"felt", "kontor", "admin"}


def prompt_required(label: str) -> str:
    while True:
        value = input(label).strip()

        if value:
            return value

        print("Feltet må ikke være tomt.")


def prompt_role() -> str:
    while True:
        role = input(
            "Rolle (felt/kontor/admin): "
        ).strip().lower()

        if role in VALID_ROLES:
            return role

        print(
            "Ugyldig rolle. Vælg felt, kontor eller admin."
        )

def prompt_password(role: str) -> str:
    while True:
        if role == "felt":
            password = getpass.getpass(
                "Start-PIN: "
            )
        else:
            password = getpass.getpass(
                "Start-password: "
            )

        valid, message = password_is_valid(
            password,
            role,
        )

        if not valid:
            print(message)
            continue

        confirmation = getpass.getpass(
            "Gentag startkode: "
        )

        if password != confirmation:
            print("De to koder er ikke ens.")
            continue

        return password


def main() -> None:
    username = prompt_required(
        "Brugernavn: "
    ).lower()

    display_name = prompt_required(
        "Visningsnavn: "
    )

    role = prompt_role()
    password = prompt_password(role)

    user = User(
        username=username,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
        must_change_password=True,
    )

    with SessionLocal() as session:
        session.add(user)

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            print(
                f"Brugernavnet '{username}' findes allerede."
            )
            return

        session.refresh(user)

        print(
            f"Bruger oprettet: "
            f"{user.username} "
            f"({user.role})"
        )
        print(
            "Brugeren skal vælge en ny kode ved første login."
        )


if __name__ == "__main__":
    main()