from openai import OpenAI
import os


TYRKIS = "\033[96m"
RESET = "\033[0m"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise RuntimeError("MISTRAL_API_KEY mangler i miljøvariablerne")


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
    prompt,
    model=None,
    max_tokens=800,
    temperature=0,
):
    model = model or DEFAULT_MODEL

    print("Sender forespørgsel til Mistral...")
    print("Model:", model)
    print("Prompt størrelse:", len(prompt))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print("Svar modtaget fra Mistral")

    return response.choices[0].message.content


def ask_mistral_fast(
    prompt,
    max_tokens=300,
    temperature=0,
):
    return ask_mistral(
        prompt=prompt,
        model=FAST_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )


if __name__ == "__main__":
    while True:
        question = input("\n🤖 Spørg AI: ")

        if question.lower() in ["exit", "quit", "stop"]:
            break

        try:
            answer = ask_mistral(question)
            print(f"\n{TYRKIS}💡 AI: {answer}{RESET}\n")
        except Exception as error:
            print(f"\nFejl ved AI-kald: {error}\n")