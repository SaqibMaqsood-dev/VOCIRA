# Vocira-Rag engine(for general purpose)

import os
import time
import socket
import asyncio
import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from bs4 import BeautifulSoup

from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from pinecone import Pinecone, ServerlessSpec
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

# CONFIGURATION


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

DATA_DIR          = "./data"
PDF_PATH          = os.path.join(DATA_DIR, "pdf")
TEXT_FILES_PATH   = os.path.join(DATA_DIR, "text_files")
URLS_FILE_PATH    = os.path.join(DATA_DIR, "urls.txt")
INDEX_NAME        = "school-bot-index"
TEMP_INDEX_NAME   = f"{INDEX_NAME}-temp"
MAX_CONTEXT_CHARS = 3000

# GLOBAL STATE

vector_store = None
retriever    = None
is_syncing   = False

# PHASE 1 — WEB SCRAPING

def get_dynamic_data(url: str):
    """Scrape a single URL using Selenium with safety checks."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except OSError:
        log.error(f"Network Error: Cannot reach {url}")
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        log.info(f"Scraping: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass

        return driver.page_source

    except Exception as e:
        log.error(f"Scraping Error for {url}: {e}")
        return None

    finally:
        if driver:
            driver.quit()


# PHASE 2 — KNOWLEDGE BASE ASSEMBLY

async def assemble_knowledge_base():
    """Load PDFs, text files, and live web data into chunks."""
    all_docs = []

    # 1. Load PDFs
    if os.path.exists(PDF_PATH) and os.listdir(PDF_PATH):
        pdf_loader = PyPDFDirectoryLoader(PDF_PATH)
        all_docs.extend(pdf_loader.load())
        log.info(f"PDFs loaded from {PDF_PATH}")

    # 2. Load Text Files
    if os.path.exists(TEXT_FILES_PATH) and os.listdir(TEXT_FILES_PATH):
        text_loader = DirectoryLoader(
            TEXT_FILES_PATH, glob="./*.txt", loader_cls=TextLoader
        )
        all_docs.extend(text_loader.load())
        log.info(f"Text files loaded from {TEXT_FILES_PATH}")

    # 3. Parallel Web Scraping
    if os.path.exists(URLS_FILE_PATH):
        with open(URLS_FILE_PATH, "r") as f:
            urls = [line.strip() for line in f if line.strip()]

        if urls:
            log.info(f"Scraping {len(urls)} URLs in parallel...")
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [loop.run_in_executor(executor, get_dynamic_data, url) for url in urls]
                results = await asyncio.gather(*futures)

            for url, html in zip(urls, results):
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.extract()
                    clean_text = soup.get_text(separator="\n", strip=True)
                    all_docs.append(Document(
                        page_content=clean_text,
                        metadata={"source": url, "type": "web_live"}
                    ))
            log.info("All URLs processed.")

    # 4. Chunking
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(all_docs)
    log.info(f"Total chunks ready: {len(chunks)}")
    return chunks


# PHASE 3 — VECTOR INDEXING (PINECONE)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def upload_to_pinecone(chunks, embeddings, index_name: str):
    """Upload chunks to Pinecone with automatic retry."""
    return PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name
    )


def wait_for_index(pc: Pinecone, index_name: str):
    """Wait until Pinecone index is ready."""
    while not pc.describe_index(index_name).status["ready"]:
        time.sleep(1)


async def build_vector_store(chunks):
    """Safe swap pattern — upload first, delete old after confirmation."""
    log.info("Initializing embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_spec = ServerlessSpec(cloud="aws", region="us-east-1")

    if INDEX_NAME not in pc.list_indexes().names():
        # Fresh index
        log.info(f"Creating new production index: {INDEX_NAME}")
        pc.create_index(name=INDEX_NAME, dimension=384, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)
        store = upload_to_pinecone(chunks, embeddings, INDEX_NAME)

    else:
        # Safe swap — upload to temp first, then replace production
        log.info("Existing index found. Starting safe swap...")

        if TEMP_INDEX_NAME not in pc.list_indexes().names():
            pc.create_index(name=TEMP_INDEX_NAME, dimension=384, metric="cosine", spec=index_spec)
            wait_for_index(pc, TEMP_INDEX_NAME)

        log.info(f"Uploading {len(chunks)} chunks to staging index...")
        upload_to_pinecone(chunks, embeddings, TEMP_INDEX_NAME)
        log.info("Staging upload confirmed. Replacing production index...")

        pc.delete_index(INDEX_NAME)
        time.sleep(3)

        pc.create_index(name=INDEX_NAME, dimension=384, metric="cosine", spec=index_spec)
        wait_for_index(pc, INDEX_NAME)

        store = upload_to_pinecone(chunks, embeddings, INDEX_NAME)
        pc.delete_index(TEMP_INDEX_NAME)
        log.info("Staging index cleaned up.")

    log.info(f"Pinecone synced — {len(chunks)} chunks indexed.")
    return store


# PHASE 4 — RETRIEVAL + GROQ REASONING

def search_knowledge_base(query: str):
    """Fetch relevant chunks and their sources from Pinecone."""
    try:
        if not retriever:
            return "Retriever is not initialized. Please run /sync-database first.", []

        docs = retriever.invoke(query)
        if not docs:
            return "", []

        context_parts = []
        sources = set()

        for doc in docs:
            context_parts.append(doc.page_content)
            sources.add(doc.metadata.get("source", "Internal Records"))

        return "\n".join(context_parts), list(sources)

    except Exception as e:
        log.error(f"Retrieval error: {e}")
        return f"Database Error: {str(e)}", []


def ask_vocira(user_query: str):
    """Core RAG logic — retrieve context and generate answer via Groq."""
    context, sources = search_knowledge_base(user_query)

    # No context found — clean rejection
    if not context.strip():
        return "I'm sorry, I couldn't find any verified information about this in the school records."

    # Context window guard
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...[truncated]"

    system_prompt = f"""You are Vocira, the official AI Assistant for 'The Educators'.
Use the following verified context to answer the user's question.

RULES:
1. Be concise, helpful, and professional.
2. If the context does not contain the answer, politely say you don't have that information.
3. Never make up facts.

CONTEXT:
{context}"""

    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    for attempt in range(3):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_query}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            answer = response.choices[0].message.content  
            return answer

        except Exception as e:
            status = getattr(e, "status_code", None)
            if status in (503, 429):
                log.warning(f"API rate limited. Retry {attempt + 1}/3...")
                time.sleep(3 * (attempt + 1))
                continue
            log.error(f"Groq error: {e}")
            return f"Unexpected Error: {str(e)}"

    return "Service unavailable after 3 attempts. Please try again later."


# BACKGROUND SYNC WORKER

def sync_pipeline_worker():
    """Background worker — scrape, chunk, and re-index Pinecone."""
    global vector_store, retriever, is_syncing
    is_syncing = True
    try:
        log.info("--- [Background Sync] Started ---")

        # New event loop for background thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        chunks = loop.run_until_complete(assemble_knowledge_base())
        store  = loop.run_until_complete(build_vector_store(chunks))
        loop.close()

        vector_store = store
        retriever    = vector_store.as_retriever(search_kwargs={"k": 5})

        log.info("--- [Background Sync] Completed Successfully ---")

    except Exception as e:
        log.error(f"Background sync crashed: {e}")
    finally:
        is_syncing = False


# FASTAPI — STARTUP + ENDPOINTS

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Instantly connect to existing Pinecone index on boot."""
    global vector_store, retriever

    log.info("===== VOCIRA STARTING UP =====")

    try:
        embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
        pc         = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

        if INDEX_NAME in pc.list_indexes().names():
            vector_store = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)
            retriever    = vector_store.as_retriever(search_kwargs={"k": 5})
            log.info("Connected to existing Pinecone index.")
        else:
            log.warning("No index found. Hit POST /sync-database to build knowledge base.")

    except Exception as e:
        log.error(f"Startup Pinecone connection failed: {e}")

    log.info("===== VOCIRA READY =====")
    yield
    log.info("===== VOCIRA SHUTTING DOWN =====")


app = FastAPI(
    title="Vocira RAG API",
    description="AI Assistant for The Educators School",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────────

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
    """Manually trigger scraping and Pinecone re-indexing in background."""
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
    answer = ask_vocira(request.question)
    return AskResponse(answer=answer)


# RUN

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)