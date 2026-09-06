# SentinelCache

SentinelCache is a high-performance, cloud-native AI API gateway that combines complexity-aware semantic caching with dynamic LLM routing to optimize latency, cost, and response quality across multi-provider LLM deployments.

## Directory Structure

```text
sentinelcache/
├── gateway/       # FastAPI app, request handling, Qdrant cache client
├── embedding/     # Vector embedding model wrappers (SentenceTransformers)
├── routing/       # Intent risk classification & dynamic routing logic
├── eval/          # Benchmark datasets & evaluation scripts (test_risk_classifier.py)
├── dashboard/     # Prometheus & Grafana dashboard configurations
└── docs/          # Technical report drafts & benchmark logs
```

---

## Phase 1: Semantic Caching Core

In Phase 1, SentinelCache introduced vector semantic caching to intercept semantically identical user prompts before hitting external LLMs using `sentence-transformers/all-MiniLM-L6-v2` and Qdrant.

---

## Phase 2: Adaptive Thresholding

Phase 2 replaces static similarity thresholding with intent- and risk-aware adaptive similarity thresholding. High-risk operational prompts (e.g. `cancel`, `delete`, `downgrade`) use strict thresholds ($\approx 0.957 - 0.99$) to prevent dangerous false-positive cache hits, while low-risk informational prompts use looser thresholds ($\approx 0.88 - 0.902$) to maximize cache hit rates for paraphrased queries.

### Risk Classification Heuristic (`routing/risk_classifier.py`)
- **High-Risk Verbs** (`cancel`, `delete`, `downgrade`, `refund`, etc.): Base `risk_score = 0.70` (+ `0.15` if negation words like `don't` or `not` are present).
- **Low-Risk Informational Markers** (`what`, `how`, `explain`, `define`): `risk_score = 0.10` (short prompts) to `0.30` (longer prompts).
- **Default Bucket**: `risk_score = 0.50`.

### Linear Threshold Mapping Formula (`gateway/cache.py`)
`effective_threshold = 0.88 + (0.11 * risk_score)`
- `risk_score = 0.0` $\rightarrow$ `threshold = 0.88`
- `risk_score = 0.70` $\rightarrow$ `threshold = 0.9570` (Prevents false hits on "Cancel" vs "Downgrade")
- `risk_score = 1.0` $\rightarrow$ `threshold = 0.99`

---

## Setup & Running Guide

### 1. Environment Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Start Qdrant Vector Database

```bash
docker compose up -d
```

### 3. Run Risk Classifier Evaluation Suite

```bash
python eval/test_risk_classifier.py
```

### 4. Launch Gateway Server

```bash
uvicorn gateway.main:app --reload --port 8000
```

---

## Sample Request & Response Telemetry

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d "{\"prompt\": \"Cancel my subscription immediately.\"}"
```

**JSON Response Payload:**

```json
{
  "response": "To cancel your subscription, please navigate to Account Settings > Billing...",
  "latency": 1.2541,
  "source": "llm",
  "cache_lookup_latency_seconds": 0.0194,
  "risk_assessment": {
    "risk_score": 0.7,
    "matched_signals": [
      "high_risk_verb:cancel"
    ],
    "effective_threshold": 0.957
  }
}
```
