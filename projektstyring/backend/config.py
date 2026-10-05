from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(
    dotenv_path=PROJECT_ROOT / ".env",
    override=False,
)


def require_env(name: str) -> str:
    value = os.environ.get(name)

    if not value:
        raise RuntimeError(f"{name} er ikke konfigureret.")

    return value
