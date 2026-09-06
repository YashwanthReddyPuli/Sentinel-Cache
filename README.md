# SentinelCache

SentinelCache is a high-performance, cloud-native AI API gateway that combines complexity-aware semantic caching with dynamic LLM routing to optimize latency, cost, and response quality across multi-provider LLM deployments.

## Directory Structure

```text
sentinelcache/
├── gateway/       # FastAPI app, request handling, Qdrant cache client, provider dispatch
├── embedding/     # Vector embedding model wrappers (SentenceTransformers)
├── routing/       # Intent risk classification & dynamic multi-provider routing logic
├── eval/          # Benchmark datasets & evaluation scripts (test_risk_classifier.py)
├── dashboard/     # Prometheus & Grafana dashboard configurations
└── docs/          # Technical report drafts & benchmark logs
```

---

## Phase 1: Semantic Caching Core

Vector semantic caching intercepts semantically identical user prompts before hitting external LLMs using `sentence-transformers/all-MiniLM-L6-v2` and Qdrant.

---

## Phase 2: Adaptive Thresholding

Adaptive thresholding scales similarity thresholds based on intent risk score:
`effective_threshold = 0.88 + (0.11 * risk_score)`
- High-risk operational prompts (`cancel`, `delete`, `downgrade`) use strict thresholds ($\approx 0.957 - 0.99$).
- Low-risk informational prompts (`what`, `explain`, `define`) use looser thresholds ($\approx 0.88 - 0.902$).

---

## Phase 3: Dynamic Model Capability Routing & Fallback

Phase 3 introduces dynamic capability-based model tiering:
- **`fast_cheap` Tier (Groq `openai/gpt-oss-20b`)**: Routed when `risk_score < 0.50` (simple informational queries). Pricing: $0.05 / 1M input tokens, $0.08 / 1M output tokens.
- **`capable_expensive` Tier (Groq-Capable `openai/gpt-oss-120b`)**: Routed when `risk_score >= 0.50` (complex operational / sensitive actions requiring deep reasoning). Pricing: $0.50 / 1M input tokens, $0.80 / 1M output tokens.

### Automated Fallback Resilience & Startup Safety
- **Loud Startup Key Validation**: The gateway validates all provider `api_key_env_var` keys at startup and fails fast with a `RuntimeError` if required keys are missing or unconfigured.
- **Outage Fallback**: If a primary provider model call fails (HTTP 5xx, 4xx model error, or timeout), SentinelCache automatically catches the exception, logs detailed diagnostic telemetry, and retries against a fallback healthy provider model without failing the request to the client.

---

## Setup & Running Guide

### 1. Environment Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key
OPENAI_API_KEY=sk_your_openai_api_key
```

### 3. Start Qdrant Vector Database

```bash
docker compose up -d
```

### 4. Launch Gateway Server

```bash
uvicorn gateway.main:app --reload --port 8000
```

---

## Sample Request Telemetry & Response Schema

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"What is the capital of France?\"}"
```

**JSON Response Payload:**

```json
{
  "response": "The capital of France is Paris.",
  "latency": 0.4521,
  "source": "llm",
  "cache_lookup_latency_seconds": 0.0124,
  "risk_assessment": {
    "risk_score": 0.1,
    "matched_signals": [
      "informational_marker:what"
    ],
    "effective_threshold": 0.891
  },
  "routing_decision": {
    "provider": "Groq",
    "model": "openai/gpt-oss-20b",
    "tier": "fast_cheap",
    "reasoning": "Risk score 0.10 < 0.50 cutoff -> Selected fast_cheap tier. Selected healthy provider 'Groq'."
  },
  "estimated_cost_usd": 0.00000155
}
```
