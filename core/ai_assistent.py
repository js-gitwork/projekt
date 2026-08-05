from __future__ import annotations

import os

from openai import OpenAI


TYRKIS = "\033[96m"
RESET = "\033[0m"


DEBUG_AI = (
    os.getenv("DEBUG_AI", "1").strip() == "1"
)


def debug(*args, **kwargs):
    """
    Udskriver kun debug-information når DEBUG_AI er slået til.
    """
    if DEBUG_AI:
        print(*args, **kwargs)


MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise RuntimeError(
        "MISTRAL_API_KEY mangler i miljøvariablerne."
    )


DEFAULT_MODEL = os.getenv(
    "MISTRAL_DEFAULT_MODEL",
    "mistral-medium-latest",
)

FAST_MODEL = os.getenv(
    "MISTRAL_FAST_MODEL",
    "mistral-small-latest",
)


client = OpenAI(
    api_key=MISTRAL_API_KEY,
    base_url="https://api.mistral.ai/v1",
    timeout=60,
)


def ask_mistral(
    prompt: str,
    model: str | None = None,
    max_tokens: int = 800,
    temperature: float = 0,
) -> str:
    """
    Sender en prompt til Mistral og returnerer svaret.
    """

    prompt = str(prompt).strip()

    if not prompt:
        raise ValueError(
            "Prompten må ikke være tom."
        )

    model = model or DEFAULT_MODEL

    debug("Sender forespørgsel til Mistral...")
    debug("Model:", model)
    debug(
        "Prompt størrelse:",
        len(prompt),
        "tegn",
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    debug("Svar modtaget fra Mistral")

    if response.usage:
        debug(
            "Tokenforbrug:",
            f"input={response.usage.prompt_tokens}",
            f"output={response.usage.completion_tokens}",
            f"total={response.usage.total_tokens}",
        )

    if response.choices:
        debug(
            "Finish reason:",
            response.choices[0].finish_reason,
        )

    if not response.choices:
        raise RuntimeError(
            "Mistral returnerede ingen svar."
        )

    answer = response.choices[0].message.content

    if answer is None:
        raise RuntimeError(
            "Mistral returnerede et tomt svar."
        )

    return answer


def ask_mistral_fast(
    prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0,
) -> str:
    """
    Hurtig model til Roerbot.

    2000 er et maksimum og ikke et fast tokenforbrug.
    """
    return ask_mistral(
        prompt=prompt,
        model=FAST_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def run_interactive_shell():
    while True:
        question = input("\n🤖 Spørg AI: ").strip()

        if question.casefold() in {
            "exit",
            "quit",
            "stop",
        }:
            break

        if not question:
            continue

        try:
            answer = ask_mistral(question)

            print(
                f"\n{TYRKIS}"
                f"💡 AI: {answer}"
                f"{RESET}\n"
            )

        except Exception as error:
            print(
                f"\nFejl ved AI-kald: {error}\n"
            )


if __name__ == "__main__":
    run_interactive_shell()