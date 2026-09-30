#PDF + text + URL loading
import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.microservices.livekit_Rag_services.services.rag_engine.config import PDF_PATH, TEXT_FILES_PATH, URLS_FILE_PATH
from backend.microservices.livekit_Rag_services.services.rag_engine.fetcher import get_dynamic_data

log = logging.getLogger(__name__)

_ERROR_MARKERS = (
    "404 not found",
    "403 forbidden",
    "page not found",
    "the requested url",
    "500 internal server error",
    "502 bad gateway",
    "503 service unavailable",
)

# Anything shorter carries no real information.
_MIN_PAGE_CHARS = 200


def _is_error_page(soup: BeautifulSoup, text: str) -> bool:
    title = (soup.title.get_text(strip=True) if soup.title else "").lower()
    head = text[:300].lower()
    if any(marker in title or marker in head for marker in _ERROR_MARKERS):
        return True
    return len(text) < _MIN_PAGE_CHARS


async def assemble_knowledge_base(
    pdf_path: str = PDF_PATH,
    text_path: str = TEXT_FILES_PATH,
    urls_path: str = URLS_FILE_PATH,
):
    """Load PDFs, text files, and live web data into chunks.

    The folders are one school's (services/tenants.py); the default
    is the first school's, as it always was.
    """
    all_docs = []

    # 1.Load PDFs — blocking disk I/O, so we send it into to_thread,
    # so that the event loop stays free for concurrent /ask requests.
    if os.path.exists(pdf_path) and os.listdir(pdf_path):
        pdf_loader = PyPDFDirectoryLoader(pdf_path)
        pdf_docs = await asyncio.to_thread(pdf_loader.load)
        all_docs.extend(pdf_docs)
        log.info(f"PDFs loaded from {pdf_path}")

    # 2. Load Text Files — same reason to_thread 
    if os.path.exists(text_path) and os.listdir(text_path):
        text_loader = DirectoryLoader(
            text_path, glob="./*.txt", loader_cls=TextLoader
        )
        text_docs = await asyncio.to_thread(text_loader.load)
        all_docs.extend(text_docs)
        log.info(f"Text files loaded from {text_path}")

    # 3. Parallel Web Scraping
    if os.path.exists(urls_path):
        with open(urls_path, "r") as f:
            urls = [line.strip() for line in f if line.strip()]

        if urls:
            log.info(f"Scraping {len(urls)} URLs in parallel...")
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [loop.run_in_executor(executor, get_dynamic_data, url) for url in urls]
                results = await asyncio.gather(*futures)

            for url, html in zip(urls, results):
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.extract()
                    clean_text = soup.get_text(separator="\n", strip=True)

                    # A dead link still returns a page. The scraper cannot
                    # see the status code, so a "404 Not Found" page went
                    # into the index - and, being short and generic, it
                    # came out on top for questions like "where is the
                    # school?", pushing the real answer down.
                    if _is_error_page(soup, clean_text):
                        log.warning("Skipping %s - it is an error page", url)
                        continue

                    all_docs.append(Document(
                        page_content=clean_text,
                        metadata={"source": url, "type": "web_live"}
                    ))
            log.info("All URLs processed.")

    # 4. Chunking — this is also CPU-bound work for large document sets,
    # so we send it into to_thread, so that the event loop stays responsive
    # even during large ingestion runs.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = await asyncio.to_thread(splitter.split_documents, all_docs)
    log.info(f"Total chunks ready: {len(chunks)}")
    return chunks
