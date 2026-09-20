# SentinelCache Phase 4.5 Empirical Evaluation Results Summary

This table summarizes the performance metrics comparing baseline (no caching), fixed-threshold caching (0.92), risk-aware adaptive thresholding (0.88 - 0.99), and production hybrid mode (adaptive threshold + Negation/Entity guards) across 45 prompt pairs.

| Metric | Disabled (No Cache) | Fixed Threshold (0.92) | Adaptive Threshold (0.88-0.99) | Hybrid Guard Mode (Production) |
| :--- | :---: | :---: | :---: | :---: |
| **Total Tested Pairs** | 45 | 45 | 45 | 45 |
| **True Positives (TP)** | 0 | 5 | 5 | 3 |
| **False Positives (FP - Safety Failures)** | 0 | 5 | 2 | 0 |
| **True Negatives (TN)** | 20 | 15 | 18 | 20 |
| **False Negatives (FN)** | 25 | 20 | 20 | 22 |
| **Precision** | 0.0000 | 0.5000 | 0.7143 | 1.0000 |
| **Recall (Overall)** | 0.0000 | 0.2000 | 0.2000 | 0.1200 |
| **Recall: A1 Low-Risk Paraphrases** | 0.0000 | 0.2500 | 0.2500 | 0.1500 |
| **Recall: A2 High-Risk Paraphrases** | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| **False Positive Rate (FPR)** | 0.0000 | 0.2500 | 0.1000 | 0.0000 |
| **False Negative Rate (FNR)** | 1.0000 | 0.8000 | 0.8000 | 0.8800 |
| **Overall Cache Hit Rate** | 0.0000 | 0.2222 | 0.1556 | 0.0667 |
| **Average Latency (ms)** | 2905.26ms | 3037.05ms | 7693.53ms | 9490.19ms |
| **Median Latency (ms)** | 1646.65ms | 2070.87ms | 2401.55ms | 3443.91ms |
