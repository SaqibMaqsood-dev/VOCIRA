"""RAG test: sync ke baad jawab aa rahe hain?"""
import asyncio, io, contextlib

from backend.microservices.livekit_Rag_services.services.rag_engine.vectorstore import (
    connect_existing_store, get_index_stats,
)
from backend.microservices.livekit_Rag_services.services.rag_engine.config import INDEX_NAME
from backend.microservices.livekit_Rag_services.services.rag_engine.query import ask_vocira

QUESTIONS = [
    "What is the admission policy?",
    "What are the school timings?",
    "How can I contact the school?",
    "How many campuses does The Educators have?",
    "What is the fee structure?",
]

noise = io.StringIO()


async def main():
    stats = await get_index_stats()
    print("=" * 74)
    print(f"RAG TEST   index={stats['index']}  vectors={stats['vectors']}  top_k={stats['top_k']}")
    print("=" * 74)

    with contextlib.redirect_stdout(noise):
        retriever = connect_existing_store(index_name=INDEX_NAME)

    if retriever is None:
        print("  FAIL: retriever bana hi nahi")
        return

    ok = 0
    for q in QUESTIONS:
        with contextlib.redirect_stdout(noise):
            ans = await ask_vocira(retriever=retriever, user_query=q)
        ans = (ans or "").strip()
        # "mujhe nahi pata" type jawab ko fail ginte hain
        weak = any(p in ans.lower() for p in [
            "couldn't find", "could not find", "don't have", "do not have",
            "sorry, i", "no verified information",
        ])
        if ans and not weak:
            ok += 1
            mark = "PASS"
        else:
            mark = "WEAK"
        print(f"\n[{mark}] {q}")
        print(f"       {ans[:200]}")

    print("\n" + "=" * 74)
    print(f"  {ok}/{len(QUESTIONS)} sawalon ka asli jawab mila")
    print("=" * 74)


asyncio.run(main())
