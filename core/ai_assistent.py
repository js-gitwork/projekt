from openai import OpenAI
import os

# Mistral API (EU-server)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
client = OpenAI(
    api_key=MISTRAL_API_KEY,
    base_url="https://api.mistral.ai/v1"
)

def ask_mistral(prompt, model="mistral-medium"):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    while True:
        question = input("\n🤖 Spørg AI: ")
        if question.lower() in ["exit", "quit", "stop"]:
            break
        answer = ask_mistral(question)
        print(f"\n💡 AI: {answer}\n")
