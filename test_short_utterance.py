"""
Jo jumle live call mein bina jawab ke reh gaye, unhein seedha
pipeline ke LLM steps se guzar kar dekhein zanjeer kahan tootti hai.

    STT text -> ROUTER -> (RAG) -> ai_response_text

voice_pipeline.py:1477 par agar ai_response_text khali ho to
function chup-chaap return kar jata hai: na message save hota hai,
na TTS chalta hai. User ko lagta hai system atak gaya.
"""
import asyncio, io, contextlib, json

from backend.microservices.livekit_Rag_services.services.groq.groq import dataConverter
from backend.microservices.livekit_Rag_services.services.groq import intent_prompt
from backend.microservices.livekit_Rag_services.services.rag_engine.query import ask_vocira
from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store,
)

noise = io.StringIO()

# live call se: (jumla, kya asal mein jawab mila tha?)
CASES = [
    ("Wow.",                          False),
    ("All right.",                    False),
    ("I'm going to go.",              False),
    ("Have my fees been paid?",       True),
    ("What's your name?",             True),
    ("Where is the test going now?",  True),
]


async def route(q):
    r = await dataConverter(intent_prompt.ROUTER_PROMPT.format(user_query=q))
    return (r.choices[0].message.content or "").strip()


async def main():
    print("=" * 78)
    print("CHHOTE JUMLON KA ANJAAM")
    print("=" * 78)

    with contextlib.redirect_stdout(noise):
        retriever = connect_existing_store()

    for q, had_reply in CASES:
        with contextlib.redirect_stdout(noise):
            raw = await route(q)

        try:
            intent = json.loads(raw).get("intent", "?")
        except Exception:
            intent = f"PARSE-FAIL({raw[:40]!r})"

        answer = None
        if intent == "RAG":
            with contextlib.redirect_stdout(noise):
                try:
                    answer = await ask_vocira(retriever=retriever, user_query=q)
                except Exception as e:
                    answer = f"<<EXCEPTION {type(e).__name__}: {e}>>"

        empty = not (answer or "").strip()
        print(f"\n  jumla   : {q!r}")
        print(f"  intent  : {intent}")
        if intent == "RAG":
            print(f"  jawab   : {(answer or '')[:110]!r}")
            print(f"  khali?  : {empty}")

        # jo live mein fail hua, kya yahan bhi khali hai?
        if not had_reply and intent == "RAG" and empty:
            print("  >>> WAJAH MIL GAYI: khali jawab -> pipeline:1477 par return")
        elif not had_reply and not empty:
            print("  >>> yahan jawab aaya - masla LLM mein nahi")

    print("\n" + "=" * 78)


asyncio.run(main())
