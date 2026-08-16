from groq import Groq
from backend.microservices.livekit_Rag_services.core.config import settings

client = Groq(api_key=settings.returning_groq_api)

async def dataConverter(prompt : str) -> str:
    response =  client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {    "role"  : "user",
            "content": prompt
        }
    ],
    temperature=0
   )   
    return response
