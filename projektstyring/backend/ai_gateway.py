
"""
Fælles AI-gateway til Rørbot.

Understøtter:
- Eksisterende Mistral EU API
- OpenAI-kompatible API'er, f.eks. lokal Ollama

Ingen agent skal kende den konkrete AI-leverandør.
"""

import os

from openai import OpenAI

from core.ai_assistent import (
    client as mistral_client,
    DEFAULT_MODEL,
)


class AIGateway:
    def __init__(self):
        self.provider = os.getenv(
            "AI_PROVIDER", "mistral"
        ).strip().lower()

        if self.provider == "mistral":
            # Genbrug eksisterende EU-forbindelse.
            self.client = mistral_client
            self.model = (
                os.getenv("AI_MODEL") or DEFAULT_MODEL
            )

        elif self.provider in (
            "ollama",
            "openai_compatible",
        ):
            self.model = os.getenv("AI_MODEL")

            if not self.model:
                raise ValueError(
                    "AI_MODEL skal angives for lokal AI."
                )

            base_url = os.getenv(
                "AI_BASE_URL",
                "http://127.0.0.1:11434/v1",
            )

            self.client = OpenAI(
                api_key=os.getenv(
                    "AI_API_KEY", "local"
                ),
                base_url=base_url,
                timeout=120,
            )

        else:
            raise ValueError(
                f"Ukendt AI_PROVIDER: {self.provider}"
            )

    def chat(self, *, messages, **options):
        """
        Fælles adgang til chat og native tool calling.

        Bevarer det OpenAI-kompatible svarformat.
        Understøttede options afhænger af modellen.
        """
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **options,
        )


ai = AIGateway()
