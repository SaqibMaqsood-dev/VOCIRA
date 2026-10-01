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

    # A question and the passage that answers it are worded differently;
    # Gemini embeds each side for its role when told which one it is.
    # Both sides must use these together - an index built without them
    # has to be rebuilt (POST /sync-database) when they change.
    DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
    QUERY_TASK = "RETRIEVAL_QUERY"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
        timeout: float = 60.0,
        use_task_types: bool = True,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout = timeout
        self.use_task_types = use_task_types

    # ------------------------------------------------------------------

    def _payload(self, text: str, task: str) -> dict:
        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "outputDimensionality": self.dimensions,
        }
        if self.use_task_types:
            payload["taskType"] = task
        return payload

    def _http(self) -> httpx.Client:
        """
        One client, kept open. A new one per request meant a new TLS
        connection to Google for every question - most of the ~800 ms each
        knowledge search spent embedding the question.
        """
        client = getattr(self, "_client", None)
        if client is None:
            client = self._client = httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=4, keepalive_expiry=300),
            )
        return client

    def _post(self, path: str, body: dict) -> dict:
        url = f"{GEMINI_BASE}/models/{self.model}:{path}?key={self.api_key}"
        r = self._http().post(url, json=body)

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
                {"requests": [self._payload(t, self.DOCUMENT_TASK) for t in batch]},
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
        # The same question asked again (often - "the fee", "timings") needs
        # no second round trip; a question's vector never changes.
        cache = getattr(self, "_query_cache", None)
        if cache is None:
            cache = self._query_cache = {}
        key = " ".join(text.split()).lower()
        if key in cache:
            return cache[key]

        data = self._post("embedContent", self._payload(text, self.QUERY_TASK))
        values = data.get("embedding", {}).get("values", [])

        if not values:
            raise RuntimeError("Gemini ne khali embedding di")

        if len(cache) >= 512:
            cache.pop(next(iter(cache)))
        cache[key] = values
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
