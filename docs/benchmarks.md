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
