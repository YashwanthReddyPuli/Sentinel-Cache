# SentinelCache Benchmark Logs

Use this log file to track latency, cache hit ratios, routing decisions, and overall gateway performance across test runs.

| Date | Test Description | Latency (ms) | Notes |
| :--- | :--- | :--- | :--- |
| 2026-09-06 | Baseline Groq llama-3.1-8b-instant passthrough | -- | Initial Phase 0 verification |
| 2026-09-06 | Initial query: 'What is semantic caching in AI gateways?' | 3135.8 | Cache MISS (source: llm, lookup overhead: 94.2ms) |
| 2026-09-06 | Paraphrase: 'Can you explain semantic caching for AI gateways?' | 12.3 | Cache HIT (source: cache, similarity >= 0.92, 254x speedup) |
| 2026-09-06 | Unrelated: 'What's the weather like today?' | 1102.9 | Cache MISS (source: llm, lookup overhead: 11.1ms) |
| 2026-09-06 | Phase 2 High Risk 1: 'Cancel my subscription' | 1293.3 | Cache MISS (risk: 0.70, strict threshold: 0.9570) |
| 2026-09-06 | Phase 2 High Risk 2: 'Downgrade my subscription' | 1232.7 | Cache MISS (source: llm, strict threshold 0.9570 prevented false hit) |
| 2026-09-06 | Phase 2 Low Risk 1: 'What is semantic caching?' | 3132.9 | Cache MISS (risk: 0.10, loose threshold: 0.8910) |
| 2026-09-06 | Phase 2 Low Risk 2: 'Can you explain semantic caching?' | 13.7 | Cache HIT (source: cache, loose threshold 0.8910 allowed hit) |
| 2026-09-06 | Phase 3 Low Risk: 'What is the capital of Germany?' | 982.7 | Routed to fast_cheap (Groq `openai/gpt-oss-20b`, $0.00001006 USD) |
| 2026-09-06 | Phase 3 High Risk: 'Revoke all user permissions immediately' | 1190.8 | Routed to capable_expensive (Groq-Capable `openai/gpt-oss-120b`, $0.00017930 USD, NO fallback) |
| 2026-09-06 | Phase 3 Outage Fallback: 'What is the speed of sound in air?' | 1317.9 | Primary Groq failed -> Fallback SUCCESS to Groq-Secondary (qwen3.6-27b, $0.00004136 USD) |

## Lessons Learned & Architectural Safety Enhancements (Phase 3 Debugging)

### Single-Provider Free-Tier Capability Model Routing
- **Scope Alignment**: Paid external provider keys (such as OpenAI) are out of scope for non-funded deployment budgets. Rather than silently masking invalid/missing external keys, Phase 3 dynamic routing was re-architected to perform capability-based model tiering using Groq's model spectrum:
  - **`fast_cheap` Tier**: `openai/gpt-oss-20b` ($0.05 / 1M input, $0.08 / 1M output).
  - **`capable_expensive` Tier**: `openai/gpt-oss-120b` ($0.50 / 1M input, $0.80 / 1M output).
- **Loud Startup Key Validation**: Added a mandatory startup safety check in `gateway/main.py`. The gateway verifies that all configured provider `api_key_env_var` keys are non-empty and valid. If any key is missing or set to placeholder, gateway startup **fails immediately with a loud `RuntimeError`**, preventing silent key borrowing or fallback degradation.
- **Cost Differential Telemetry**: Both tiers hit Groq using `GROQ_API_KEY`, but token costs reflect real model parameter differentials (17.8x cost difference for high-risk complex reasoning on 120B model vs 20B fast model).

