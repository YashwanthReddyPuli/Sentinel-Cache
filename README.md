# SentinelCache: Cloud-Native AI API Gateway with Adaptive Semantic Caching & Multi-Provider LLM Routing

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red.svg)](https://qdrant.tech/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**SentinelCache** is an enterprise-grade, cloud-native AI API Gateway designed to optimize cost, latency, and security for high-throughput LLM deployments. By integrating **intent risk classification**, **dynamic similarity thresholding**, **tiered multi-provider routing**, and **automated fallback resilience**, SentinelCache safely accelerates repetitive prompts while protecting against costly false cache hits on high-risk operational actions.

---

## 🏛️ System Architecture Overview

```text
                               ┌─────────────────────────────────────────┐
                               │           Client HTTP Request           │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │      FastAPI Gateway Interceptor        │
                               └────────────────────┬────────────────────┘
                                                    │
                                ┌───────────────────┴───────────────────┐
                                │                                       │
                                ▼                                       ▼
                   ┌──────────────────────────┐           ┌──────────────────────────┐
                   │ Intent Risk Classifier   │           │ Vector Embedding Model   │
                   │ (Heuristics & Signals)   │           │ (all-MiniLM-L6-v2)       │
                   └────────────┬─────────────┘           └────────────┬─────────────┘
                                │                                       │
                                │ Risk Score (0.0 - 1.0)                │ 384-dim Vector
                                ▼                                       ▼
                   ┌──────────────────────────────────────────────────────────┐
                   │               Dynamic Adaptive Thresholding              │
                   │         effective_threshold = 0.88 + (0.11 * risk)       │
                   └────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                               ┌──────────────────────────────────────────┐
                               │       Qdrant Vector Database Search      │
                               └────────────────┬─────────────────────────┘
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       │                                                 │
            Similarity >= Threshold                            Similarity < Threshold
                       │                                                 │
                       ▼                                                 ▼
             ┌──────────────────┐                              ┌──────────────────┐
             │    CACHE HIT     │                              │    CACHE MISS    │
             │  Bypass LLM Call │                              │  Dynamic Router  │
             └─────────┬────────┘                              └────────┬─────────┘
                       │                                                │
                       │                                  ┌─────────────┴─────────────┐
                       │                                  │                           │
                       │                        Risk < 0.50                   Risk >= 0.50
                       │                                  │                           │
                       │                                  ▼                           ▼
                       │                        ┌──────────────────┐        ┌──────────────────┐
                       │                        │  fast_cheap Tier │        │ capable_expensive│
                       │                        │   (Groq 20B)     │        │   (Groq 120B)    │
                       │                        └─────────┬────────┘        └─────────┬────────┘
                       │                                  │                           │
                       │                                  └─────────────┬─────────────┘
                       │                                                │
                       │                                                ▼
                       │                                   ┌──────────────────────────┐
                       │                                   │ Automated Outage Fallback│
                       │                                   └────────────┬─────────────┘
                       │                                                │
                       ▼                                                ▼
             ┌────────────────────────────────────────────────────────────────────┐
             │                 Unified JSON Telemetry Response                    │
             └────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```text
sentinelcache/
├── gateway/                 # Core API Gateway implementation
│   ├── main.py              # FastAPI endpoints, middleware & lifecycles
│   └── cache.py             # Qdrant client, collection mgmt & lookup logic
├── embedding/               # Vector embedding abstraction layer
│   └── embedder.py          # SentenceTransformers model wrapper (384-dim)
├── routing/                 # Dynamic classification & provider routing engine
│   ├── risk_classifier.py   # Intent risk scoring & signal extraction
│   ├── provider_registry.py # Provider health checking & credential validator
│   └── router.py            # Tiered model selection & cost calculator
├── eval/                    # Phase 4 Empirical Evaluation Benchmark Suite
│   ├── benchmark_dataset.json# 45 labeled prompt pairs (A1, A2, B categories)
│   ├── benchmark_dataset.py # Benchmark dataset generation script
│   ├── run_benchmark.py     # Isolated per-pair benchmark execution engine
│   ├── plot_results.py      # Matplotlib evaluation chart rendering scripts
│   ├── compare_embedding_models.py # MiniLM vs mpnet diagnostic comparison
│   ├── results.json         # Raw benchmark output telemetry
│   └── results_summary.md   # Generated Markdown benchmark summary table
├── dashboard/               # Prometheus metrics & Grafana dashboard specs
├── docs/                    # Architectural diagrams & design documentation
├── docker-compose.yml       # Qdrant vector database container setup
└── requirements.txt         # Python dependency specification
```

---

## ⚡ Core Features & Key Pipeline Phases

### Phase 1: Semantic Caching Core
Intercepts incoming prompts and compares vector embeddings against historical queries stored in **Qdrant** using `sentence-transformers/all-MiniLM-L6-v2`. Bypasses LLM inference on high-confidence semantic matches, reducing response times to **~200ms**.

### Phase 2: Adaptive Risk-Aware Thresholding
Static similarity thresholds fail on operational queries where minor wording changes alter intent. SentinelCache dynamically computes similarity cutoffs based on prompt risk score:
$$\text{effective\_threshold} = 0.88 + (0.11 \times \text{risk\_score})$$
- **High-Risk Actions** (`cancel`, `delete`, `refund`, `revoke`): Strict thresholds ($\approx 0.957 - 0.99$).
- **Low-Risk Informational** (`what`, `explain`, `define`): Permissive thresholds ($\approx 0.88 - 0.902$).

### Phase 3: Dynamic Model Tiering & Automated Fallback Resilience
- **Tiered Model Routing**:
  - **`fast_cheap` Tier (Groq 20B)**: Auto-selected when $\text{risk\_score} < 0.50$ (\$0.05 / 1M input tokens).
  - **`capable_expensive` Tier (Groq 120B)**: Auto-selected when $\text{risk\_score} \ge 0.50$ (\$0.50 / 1M input tokens).
- **Automated Fallback**: Automatically detects upstream provider errors (HTTP 4xx/5xx, timeouts, rate limits) and seamlessly retries against healthy fallback models without user disruption.
- **Startup Credential Guard**: Loud startup validation that aborts gateway initialization if any configured provider API key is missing or invalid.

### Phase 4: Empirical Evaluation Benchmark
Empirical evaluation engine assessing caching accuracy, safety violations, and latencies across **45 labeled prompt pairs** (135 total evaluation runs).

---

## 📊 Phase 4 Empirical Evaluation Results

Evaluated across **45 prompt pairs**:
- **Category A1**: 20 Low-Risk True Paraphrases (`should_cache_hit`)
- **Category A2**: 5 High-Risk True Paraphrases (`should_cache_hit`)
- **Category B**: 20 Intent-Distinct / Semantically-Adjacent Pairs (`should_NOT_cache_hit`)

### Performance Comparison Matrix

| Metric | Disabled (No Cache) | Fixed Threshold (0.92) | Adaptive Threshold (0.88-0.99) | Impact of Adaptive Caching |
| :--- | :---: | :---: | :---: | :---: |
| **Total Tested Pairs** | 45 | 45 | 45 | 135 total evaluation runs |
| **True Positives (TP)** | 0 | 5 | 5 | High-confidence hits preserved |
| **False Positives (FP - Safety Failures)** | 0 | 5 | **2** | **60% reduction in dangerous cache hits** |
| **True Negatives (TN)** | 20 | 15 | **18** | **20% increase in correct cache misses** |
| **False Negatives (FN)** | 25 | 20 | 20 | Safety-first bias on operational actions |
| **Precision** | 0.0000 | 0.5000 | **0.7143** | **+42.8% improvement in hit accuracy** |
| **Recall (Overall)** | 0.0000 | 0.2000 | 0.2000 | Baseline embedding resolution limit |
| **Recall: Low-Risk Paraphrases (A1)** | 0.0000 | 0.2500 | 0.2500 | Informational queries cached successfully |
| **Recall: High-Risk Paraphrases (A2)** | 0.0000 | 0.0000 | 0.0000 | Safety enforcement on sensitive actions |
| **False Positive Rate (FPR)** | 0.0000 | 0.2500 | **0.1000** | **FPR reduced from 25% to 10%** |
| **Median Response Latency (ms)** | 2291.27ms | 2222.24ms | **1518.52ms** | **33.7% faster median latency** |

---

## 🔍 Diagnostic Insights: Embedding Separability Ceiling

Our diagnostic investigation ([`eval/compare_embedding_models.py`](eval/compare_embedding_models.py)) revealed a critical empirical insight regarding vector similarity caching:

1. **The Negation & Entity Swap Problem**:
   Dense embedding models like `all-MiniLM-L6-v2` produce cosine similarity scores of **0.9716** on single-word negation flips (e.g., *"Revoke API keys"* vs *"Do NOT revoke API keys"*).
2. **Dense Vector Overlap**:
   Because structural paraphrases produce similarities between **0.64** and **0.94**, Category A and Category B distributions overlap completely. Dense embedding cosine similarity alone has a mathematical ceiling when distinguishing negations.
3. **Model Comparison (`MiniLM` vs `mpnet-base`)**:
   Upgrading to `all-mpnet-base-v2` (110M params) yielded an identical overlap (Max Category B score remained **0.9848**), demonstrating that scaling vector dimensions alone cannot resolve negation ambiguity — validating SentinelCache's hybrid risk-aware thresholding approach.

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+
- Docker Desktop (for Qdrant Vector Database)
- Groq API Key ([Get one here](https://console.groq.com/keys))

### 2. Environment Setup
```bash
# Clone repository
git clone https://github.com/YashwanthReddyPuli/Sentinel-Cache.git
cd Sentinel-Cache

# Create and activate virtual environment
python -m venv .venv
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variable Configuration
Create a `.env` file in the root directory:
```env
# Groq API Credentials
GROQ_API_KEY=gsk_your_groq_api_key_here

# Qdrant Vector Store Host Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### 4. Start Qdrant Vector Database Container
```bash
docker compose up -d
```

### 5. Launch SentinelCache Gateway
```bash
uvicorn gateway.main:app --reload --host 127.0.0.1 --port 8000
```
*The gateway will perform a startup health validation of provider API keys and connect to Qdrant.*

---

## 📡 Telemetry & API Usage Examples

### Standard Request (Adaptive Mode)
```bash
curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "What is the capital of Germany?"}'
```

### Response Schema & Telemetry Payload
```json
{
  "response": "The capital of Germany is Berlin.",
  "latency": 0.218,
  "source": "cache",
  "cache_lookup_latency_seconds": 0.0112,
  "risk_assessment": {
    "risk_score": 0.2,
    "matched_signals": [
      "informational_marker:what"
    ],
    "effective_threshold": 0.902
  },
  "routing_decision": {
    "provider": "Groq",
    "model": "openai/gpt-oss-20b",
    "tier": "fast_cheap",
    "reasoning": "Risk score 0.20 < 0.50 cutoff -> Selected fast_cheap tier. (Served from cache: LLM call bypassed, mode='adaptive')."
  },
  "estimated_cost_usd": 0.0
}
```

### Running Benchmark & Diagnostic Analysis Scripts
```bash
# Execute Phase 4 Benchmark Suite (45 pairs x 3 modes)
python eval/run_benchmark.py

# Generate Evaluation PNG Charts
python eval/plot_results.py

# Run MiniLM vs mpnet Model Comparison Analysis
python eval/compare_embedding_models.py
```

---

## 📜 License & Citation

Distributed under the MIT License. See `LICENSE` for details.
