#PDF + text + URL loading
import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFDirectoryLoader, DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_engine.config import PDF_PATH, TEXT_FILES_PATH, URLS_FILE_PATH
from rag_engine.fetcher import get_dynamic_data

log = logging.getLogger(__name__)


async def assemble_knowledge_base():
    """Load PDFs, text files, and live web data into chunks."""
    all_docs = []

    # 1.Load PDFs — blocking disk I/O, so we send it into to_thread,
    # so that the event loop stays free for concurrent /ask requests.
    if os.path.exists(PDF_PATH) and os.listdir(PDF_PATH):
        pdf_loader = PyPDFDirectoryLoader(PDF_PATH)
        pdf_docs = await asyncio.to_thread(pdf_loader.load)
        all_docs.extend(pdf_docs)
        log.info(f"PDFs loaded from {PDF_PATH}")

    # 2. Load Text Files — same reason to_thread 
    if os.path.exists(TEXT_FILES_PATH) and os.listdir(TEXT_FILES_PATH):
        text_loader = DirectoryLoader(
            TEXT_FILES_PATH, glob="./*.txt", loader_cls=TextLoader
        )
        text_docs = await asyncio.to_thread(text_loader.load)
        all_docs.extend(text_docs)
        log.info(f"Text files loaded from {TEXT_FILES_PATH}")

    # 3. Parallel Web Scraping
    if os.path.exists(URLS_FILE_PATH):
        with open(URLS_FILE_PATH, "r") as f:
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