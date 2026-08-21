from groq import Groq
from backend.microservices.livekit_Rag_services.core.config import settings

client = Groq(api_key=settings.returning_groq_api)

async def dataConverter(prompt : str) -> str:
    response =  client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {    "role"  : "user",
            "content": prompt
        }
    ],
    temperature=0
   )   
    return response
