# Vocira — RAG Backend for The Educators

AI-powered school assistant backend. Answers student and parent queries using school PDFs, text files, and live website data.

---

## Project Structure

```
RAG_ENGINE/
├── rag/
│   ├── __init__.py
│   ├── config.py        — API keys and settings
│   ├── fetcher.py       — Web scraping (Selenium)
│   ├── ingestion.py     — PDF, text, URL loading and chunking
│   ├── query.py         — Groq LLM reasoning
│   └── vectorstore.py   — Pinecone vector database
├── data/
│   ├── pdf/             — School PDF files
│   ├── text_files/      — General info .txt files
│   └── urls.txt         — School website URLs
├── main.py              — FastAPI server and endpoints
├── .env.example         — Environment variable template
└── requirements.txt     — Python dependencies
```

---

## Requirements

- Python 3.11+
- UV package manager
- Google Chrome installed
- API keys for Pinecone, HuggingFace, Groq

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/SaqibMaqsood-dev/VOCIRA.git
cd VOCIRA
```

**2. Install dependencies**
```bash
uv add fastapi uvicorn groq pinecone langchain langchain-community langchain-huggingface langchain-pinecone beautifulsoup4 selenium webdriver-manager sentence-transformers tenacity python-dotenv nest-asyncio pypdf
```

**3. Create `.env` file**
```
PINECONE_API_KEY=your_pinecone_key
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
GROQ_API_KEY=your_groq_key
```

Get your keys from:
- Pinecone → https://app.pinecone.io
- HuggingFace → https://huggingface.co/settings/tokens
- Groq → https://console.groq.com

**4. Add school data**
```
data/pdf/           → Add school PDF files here
data/text_files/    → Add .txt files here
data/urls.txt       → Add school website URLs (one per line)
```

**5. Run the server**
```bash
uv run python main.py
```

Server starts at: `http://localhost:8000`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Server status check |
| GET | `/health` | Knowledge base status |
| POST | `/ask` | Ask a question |
| POST | `/sync-database` | Refresh knowledge base |

---

## Ask a Question

**Request:**
```json
{
  "question": "What is the admission procedure?"
}
```

**Response:**
```json
{
  "answer": "The admission procedure at The Educators involves..."
}
```

---

## Frontend Integration (Next.js)

```javascript
const res = await fetch("http://localhost:8000/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: userInput })
});
const data = await res.json();
console.log(data.answer);
```

---

## Notes

- First `/sync-database` takes 3-5 minutes — scraping + indexing
- After that, server boots in seconds using existing Pinecone index
- Call `/sync-database` whenever school data is updated
- CORS is enabled for all origins by default — update for production