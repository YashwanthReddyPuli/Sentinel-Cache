# SentinelCache Phase 4 Empirical Evaluation Results Summary

This table summarizes the performance metrics comparing baseline (no caching), fixed-threshold caching (0.92), and risk-aware adaptive thresholding (0.88 - 0.99) across 45 prompt pairs.

| Metric | Disabled (No Cache) | Fixed Threshold (0.92) | Adaptive Threshold (0.88-0.99) |
| :--- | :---: | :---: | :---: |
| **Total Tested Pairs** | 45 | 45 | 45 |
| **True Positives (TP)** | 0 | 5 | 5 |
| **False Positives (FP - Costly Failures)** | 0 | 5 | 2 |
| **True Negatives (TN)** | 20 | 15 | 18 |
| **False Negatives (FN)** | 25 | 20 | 20 |
| **Precision** | 0.0000 | 0.5000 | 0.7143 |
| **Recall (Overall)** | 0.0000 | 0.2000 | 0.2000 |
| **Recall: A1 Low-Risk Paraphrases** | 0.0000 | 0.2500 | 0.2500 |
| **Recall: A2 High-Risk Paraphrases** | 0.0000 | 0.0000 | 0.0000 |
| **False Positive Rate (FPR)** | 0.0000 | 0.2500 | 0.1000 |
| **False Negative Rate (FNR)** | 1.0000 | 0.8000 | 0.8000 |
| **Overall Cache Hit Rate** | 0.0000 | 0.2222 | 0.1556 |
| **Average Latency (ms)** | 3193.1ms | 2818.11ms | 3080.75ms |
| **Median Latency (ms)** | 2291.27ms | 2222.24ms | 1518.52ms |
