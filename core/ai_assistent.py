from openai import OpenAI
import os

TYRKIS = "\033[96m"
RESET = "\033[0m"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise RuntimeError("MISTRAL_API_KEY mangler i miljøvariablerne")

client = OpenAI(
    api_key=MISTRAL_API_KEY,
    base_url="https://api.mistral.ai/v1",
    timeout=30,
)


def ask_mistral(prompt, model="mistral-small-latest"):
    print("Sender forespørgsel til Mistral...")
    print("Model:", model)
    print("Prompt størrelse:", len(prompt))

    response = client.chat.completions.create(
        model="mistral-small-latest",
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=200,
    )

    print("Svar modtaget fra Mistral")

    return response.choices[0].message.content


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