# SentinelCache

SentinelCache is a high-performance, cloud-native AI API gateway that combines complexity-aware semantic caching with dynamic LLM routing to optimize latency, cost, and response quality across multi-provider LLM deployments.

## Directory Structure

```text
sentinelcache/
├── gateway/       # FastAPI app, request handling & endpoints
├── embedding/     # Vector embedding model wrappers
├── routing/       # LLM provider registry & intelligent routing logic
├── eval/          # Benchmark datasets & evaluation scripts
├── dashboard/     # Prometheus & Grafana dashboard configurations
└── docs/          # Technical report drafts & benchmark logs
```

## Setup & Running Guide

### 1. Environment Setup

Create and activate a Python virtual environment, then install the dependencies:

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

Edit `.env` to supply your `GROQ_API_KEY`:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key
```

### 3. Start Qdrant Vector Database

Start the Qdrant service using Docker Compose:

```bash
docker compose up -d
```

Verify Qdrant is running by checking `http://localhost:6333`.

### 4. Launch the Gateway Server

Run the FastAPI gateway using Uvicorn:

```bash
uvicorn gateway.main:app --reload --port 8000
```

The server will start at `http://localhost:8000`. You can access interactive API docs at `http://localhost:8000/docs`.

### 5. Testing the Endpoint

Send a sample POST request to `/v1/chat/completions`:

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"What is semantic caching in AI gateways?\"}"
```

**Sample Response:**

```json
{
  "response": "Semantic caching in AI gateways is a technique...",
  "latency": 0.4521,
  "source": "llm"
}
```
