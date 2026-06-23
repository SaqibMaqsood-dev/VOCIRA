import asyncio
import logging
import threading
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.ingestion import assemble_knowledge_base
from rag.vectorstore import build_vector_store, connect_existing_store
from rag.query import ask_vocira

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Global State ─────────────────────────────────────────────
vector_store = None
retriever    = None
is_syncing   = False


# ── Background Sync Worker ───────────────────────────────────
def sync_pipeline_worker():
    """Background worker — scrape, chunk, and re-index Pinecone."""
    global vector_store, retriever, is_syncing
    is_syncing = True
    try:
        log.info("--- [Background Sync] Started ---")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        chunks = loop.run_until_complete(assemble_knowledge_base())
        store  = loop.run_until_complete(build_vector_store(chunks))
        loop.close()

        vector_store = store
        retriever    = vector_store.as_retriever(search_kwargs={"k": 8})

        log.info("--- [Background Sync] Completed Successfully ---")

    except Exception as e:
        log.error(f"Background sync crashed: {e}")
    finally:
        is_syncing = False


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, retriever

    log.info("===== VOCIRA STARTING UP =====")
    try:
        store, ret = connect_existing_store()
        if store:
            vector_store = store
            retriever    = ret
            log.info("Connected to existing Pinecone index.")
        else:
            log.warning("No index found. Hit POST /sync-database to build knowledge base.")
    except Exception as e:
        log.error(f"Startup Pinecone connection failed: {e}")

    log.info("===== VOCIRA READY =====")
    yield
    log.info("===== VOCIRA SHUTTING DOWN =====")


# ── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="Vocira RAG API",
    description="AI Assistant for The Educators School",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str


# ── Endpoints ────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Vocira is running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "retriever_ready": retriever is not None,
        "is_syncing": is_syncing
    }


@app.post("/sync-database")
def trigger_sync(background_tasks: BackgroundTasks):
    global is_syncing
    if is_syncing:
        raise HTTPException(status_code=409, detail="Sync is already running.")
    background_tasks.add_task(sync_pipeline_worker)
    return {"status": "queued", "message": "Database sync started in background."}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    if not retriever:
        raise HTTPException(status_code=503, detail="Knowledge base not ready. Hit /sync-database first.")
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    log.info(f"Query: {request.question}")
    answer = ask_vocira(retriever, request.question)
    return AskResponse(answer=answer)


# ── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    def open_browser():
        import time
        time.sleep(4)
        webbrowser.open("http://127.0.0.1:8000/docs")

    threading.Thread(target=open_browser).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)