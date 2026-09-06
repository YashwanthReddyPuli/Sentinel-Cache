# SentinelCache

SentinelCache is a high-performance, cloud-native AI API gateway that combines complexity-aware semantic caching with dynamic LLM routing to optimize latency, cost, and response quality across multi-provider LLM deployments.

## Directory Structure

```text
sentinelcache/
├── gateway/       # FastAPI app, request handling, Qdrant cache client
├── embedding/     # Vector embedding model wrappers (SentenceTransformers)
├── routing/       # LLM provider registry & intelligent routing logic
├── eval/          # Benchmark datasets & evaluation scripts
├── dashboard/     # Prometheus & Grafana dashboard configurations
└── docs/          # Technical report drafts & benchmark logs
```

---

## Phase 1: Semantic Caching Core

In Phase 1, SentinelCache introduces vector semantic caching to intercept semantically identical user prompts before hitting external LLMs.

### Key Capabilities Added
- **Embedding Pipeline (`embedding/embedder.py`)**: Preloads `sentence-transformers/all-MiniLM-L6-v2` at startup to encode prompt strings into 384-dimensional dense vectors.
- **Qdrant Vector Cache Client (`gateway/cache.py`)**: Wraps `qdrant-client` to automatically manage the `prompt_cache` collection configured with 384 dimensions and Cosine distance.
- **Fixed-Threshold Semantic Lookup (`gateway/main.py`)**: Performs vector similarity search with a default Cosine similarity threshold of `0.92`.
  - **Cache Miss (`source: "llm"`)**: Route prompt to Groq API (`openai/gpt-oss-20b`), store prompt/embedding/response tuple in Qdrant, and return LLM response.
  - **Cache Hit (`source: "cache"`)**: Serve response directly from Qdrant with near-zero latency, avoiding LLM token costs and network overhead.
- **Detailed Latency Breakdown**: Returns `cache_lookup_latency_seconds` alongside full request `latency`.

---

## Setup & Running Guide

### 1. Environment Setup

Create and activate a Python virtual environment, then install dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate virtual environment (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
SIMILARITY_THRESHOLD=0.92
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 3. Start Qdrant Vector Database

Start the Qdrant service using Docker Compose:

```bash
docker compose up -d
```

Verify Qdrant is running at `http://localhost:6333`.

### 4. Launch the Gateway Server

Run the FastAPI gateway using Uvicorn:

```bash
uvicorn gateway.main:app --reload --port 8000
```

The server will start at `http://localhost:8000`. You can access interactive API docs at `http://localhost:8000/docs`.

---

## Testing Semantic Caching

### Test 1: Initial Prompt (Cache MISS -> Calls Groq LLM)

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"What is semantic caching in AI gateways?\"}"
```

**Expected Output (`source: "llm"`, full round-trip latency ~1.5s):**

```json
{
  "response": "Semantic caching in AI gateways stores response vectors based on prompt meaning rather than exact text matching...",
  "latency": 1.4821,
  "source": "llm",
  "cache_lookup_latency_seconds": 0.0184
}
```

### Test 2: Paraphrased Prompt (Cache HIT -> Served Instantly from Cache)

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"Can you explain semantic caching for AI gateways?\"}"
```

**Expected Output (`source: "cache"`, near-zero latency ~0.02s):**

```json
{
  "response": "Semantic caching in AI gateways stores response vectors based on prompt meaning rather than exact text matching...",
  "latency": 0.0215,
  "source": "cache",
  "cache_lookup_latency_seconds": 0.0211
}
```
