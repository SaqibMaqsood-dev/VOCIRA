from groq import Groq

from backend.microservices.livekit_Rag_services.core.config import settings


client = Groq(
    api_key=settings.returning_groq_api
)


async def dataConverter(prompt: str):

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            temperature=0,

        )

        # ==================================================
        # DEBUG GROQ RESPONSE
        # ==================================================

        print("=" * 70)
        print("🤖 [GROQ RESPONSE]")
        print(
            f"Choices: "
            f"{len(response.choices)}"
        )

        if response.choices:

            choice = response.choices[0]

            print(
                f"Finish reason: "
                f"{choice.finish_reason}"
            )

            print(
                f"Message: "
                f"{choice.message}"
            )

            print(
                f"Content repr: "
                f"{repr(choice.message.content)}"
            )

        print("=" * 70)

        return response

    except Exception as exc:

        print("=" * 70)
        print("❌ [GROQ ERROR]")
        print(f"Error: {exc}")
        print("=" * 70)

        raise