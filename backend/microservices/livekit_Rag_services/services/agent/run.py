"""
Starts the voice agent:

    uv run --no-sync python -m backend.microservices.livekit_Rag_services.services.agent.run start

Kept tiny on purpose. On Windows every helper process (the turn
detector's inference process, the Piper process) is started fresh and
imports the main module again - when that was worker.py, each of them
loaded the whole of Vocira (1.2 GB for the turn detector alone). The
heavy imports below only run in the real main process.
"""

if __name__ == "__main__":
    from livekit.agents import cli

    from backend.microservices.livekit_Rag_services.services.agent.worker import server

    cli.run_app(server)
