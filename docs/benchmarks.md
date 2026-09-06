# SentinelCache Benchmark Logs

Use this log file to track latency, cache hit ratios, routing decisions, and overall gateway performance across test runs.

| Date | Test Description | Latency (ms) | Notes |
| :--- | :--- | :--- | :--- |
| 2026-09-06 | Baseline Groq llama-3.1-8b-instant passthrough | -- | Initial Phase 0 verification |
| 2026-09-06 | Initial query: 'What is semantic caching in AI gateways?' | 3135.8 | Cache MISS (source: llm, lookup overhead: 94.2ms) |
| 2026-09-06 | Paraphrase: 'Can you explain semantic caching for AI gateways?' | 12.3 | Cache HIT (source: cache, similarity >= 0.92, 254x speedup) |
| 2026-09-06 | Unrelated: 'What's the weather like today?' | 1102.9 | Cache MISS (source: llm, lookup overhead: 11.1ms) |
