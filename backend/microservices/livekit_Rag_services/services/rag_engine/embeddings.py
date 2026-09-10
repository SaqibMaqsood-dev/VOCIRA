"""
Embedding providers.

There are two options, chosen from .env:

    EMBEDDING_PROVIDER=local    BAAI/bge-small-en-v1.5  (384 dims)
                                needs sentence-transformers + torch (~4 GB)

    EMBEDDING_PROVIDER=gemini   gemini-embedding-001    (768 dims)
                                an HTTP call only - no heavy packages

The Gemini class implements LangChain's Embeddings interface, so
PineconeVectorStore cannot tell which one is in use.

langchain-google-genai is deliberately avoided - it gives no control
over outputDimensionality, and httpx is already in the project.
"""

import logging

import httpx
from langchain_core.embeddings import Embeddings

log = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# The most texts Gemini accepts in one request
_BATCH = 100


class GeminiEmbeddings(Embeddings):
    """Google Gemini embeddings, REST API ke zariye."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
        timeout: float = 60.0,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout

    # ------------------------------------------------------------------

    def _payload(self, text: str) -> dict:
        return {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.dimensions,
        }

    def _post(self, path: str, body: dict) -> dict:
        url = f"{GEMINI_BASE}/models/{self.model}:{path}?key={self.api_key}"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=body)

        if r.status_code != 200:
            raise RuntimeError(
                f"Gemini embeddings HTTP {r.status_code}: {r.text[:300]}"
            )
        return r.json()

    # ------------------------------------------------------------------
    # LangChain Embeddings interface
    # ------------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []

        for start in range(0, len(texts), _BATCH):
            batch = texts[start:start + _BATCH]

            data = self._post(
                "batchEmbedContents",
                {"requests": [self._payload(t) for t in batch]},
            )

            got = [e.get("values", []) for e in data.get("embeddings", [])]

            if len(got) != len(batch):
                raise RuntimeError(
                    f"Gemini ne {len(batch)} ke bajaye {len(got)} embeddings diye"
                )

            vectors.extend(got)
            log.info("Embedded %s/%s chunks", len(vectors), len(texts))

        return vectors

    def embed_query(self, text: str) -> list[float]:
        data = self._post("embedContent", self._payload(text))
        values = data.get("embedding", {}).get("values", [])

        if not values:
            raise RuntimeError("Gemini ne khali embedding di")

        return values


def build_embeddings(
    provider: str,
    *,
    local_model: str,
    gemini_api_key: str | None,
    gemini_model: str,
    gemini_dimensions: int,
):
    """Config ke mutabiq embeddings object banayein."""

    if provider == "gemini":
        log.info("Embeddings: Gemini %s (%s dims)", gemini_model, gemini_dimensions)
        return GeminiEmbeddings(
            api_key=gemini_api_key,
            model=gemini_model,
            dimensions=gemini_dimensions,
        )

    # local — torch is imported here so that the heavy import never
    # runs at all when gemini is in use
    from langchain_huggingface import HuggingFaceEmbeddings

    log.info("Embeddings: local %s", local_model)
    return HuggingFaceEmbeddings(model_name=local_model)
