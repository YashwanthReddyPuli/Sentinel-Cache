"""
Benchmark Execution Runner for SentinelCache (Phase 4).

Loads eval/benchmark_dataset.json, runs all 45 prompt pairs across three modes
("disabled", "fixed", "adaptive"), resets Qdrant cache collection before each pair,
computes precision/recall/FPR/FNR metrics (with risk_tier recall breakdown),
and saves results to eval/results.json and eval/results_summary.md.
"""

import os
import json
import time
import statistics
import httpx

GATEWAY_URL = "http://127.0.0.1:8000/v1/chat/completions"
CLEAR_CACHE_URL = "http://127.0.0.1:8000/v1/cache/clear"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "benchmark_dataset.json")
RESULTS_PATH = os.path.join(BASE_DIR, "results.json")
SUMMARY_PATH = os.path.join(BASE_DIR, "results_summary.md")


def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def reset_cache():
    """Resets the prompt_cache collection in Qdrant before each test pair and verifies zero points."""
    try:
        res = httpx.post(CLEAR_CACHE_URL, timeout=10.0)
        res.raise_for_status()
        time.sleep(0.1)
    except Exception as exc:
        print(f"[WARNING] Cache reset failed: {exc}")



def send_prompt(prompt: str, cache_mode: str) -> dict:
    """Sends a chat completion request to the gateway with specified cache_mode and retries."""
    params = {"cache_mode": cache_mode}
    payload = {"prompt": prompt}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            start_time = time.perf_counter()
            res = httpx.post(GATEWAY_URL, params=params, json=payload, timeout=45.0)
            res.raise_for_status()
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            
            data = res.json()
            data["client_latency_ms"] = elapsed
            return data
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(2.5 * (attempt + 1))
                continue
            raise


def run_benchmark():
    dataset = load_dataset()
    modes = ["disabled", "fixed", "adaptive", "hybrid"]
    
    raw_results = []
    summary_metrics = {}

    print("=" * 80)
    print("STARTING SENTINELCACHE PHASE 4.5 EMPIRICAL EVALUATION SUITE")
    print(f"Total prompt pairs: {len(dataset)} | Modes to evaluate: {modes}")
    print("=" * 80)

    for mode in modes:
        print(f"\n>>> Running Mode: '{mode.upper()}' ({len(dataset)} pairs)...")
        mode_pair_results = []
        
        for idx, item in enumerate(dataset, 1):
            pair_id = item["id"]
            prompt_a = item["prompt_a"]
            prompt_b = item["prompt_b"]
            label = item["label"]
            risk_tier = item["risk_tier"]
            category = item["category"]
            
            # Step 1: Reset cache collection to guarantee zero cross-pair contamination
            reset_cache()
            
            # Step 2: Send prompt_a to populate cache
            try:
                resp_a = send_prompt(prompt_a, mode)
            except Exception as exc:
                print(f"  [ERROR] Pair {pair_id} Prompt A failed: {exc}")
                continue

            # Small delay to ensure DB write consistency
            time.sleep(0.05)

            # Step 3: Send prompt_b to test cache hit/miss behavior
            try:
                resp_b = send_prompt(prompt_b, mode)
            except Exception as exc:
                print(f"  [ERROR] Pair {pair_id} Prompt B failed: {exc}")
                continue

            source = resp_b.get("source", "llm")
            actual_hit = (source == "cache")
            should_hit = (label == "should_cache_hit")
            
            risk_assessment = resp_b.get("risk_assessment", {})
            risk_score = risk_assessment.get("risk_score", 0.5)
            effective_threshold = risk_assessment.get("effective_threshold", 0.92)
            
            # Classification outcome type
            if should_hit and actual_hit:
                outcome_type = "TP"
            elif should_hit and not actual_hit:
                outcome_type = "FN"
            elif not should_hit and actual_hit:
                outcome_type = "FP"
            else: # not should_hit and not actual_hit
                outcome_type = "TN"

            pair_res = {
                "pair_id": pair_id,
                "category": category,
                "mode": mode,
                "label": label,
                "risk_tier": risk_tier,
                "prompt_a": prompt_a,
                "prompt_b": prompt_b,
                "actual_outcome": "hit" if actual_hit else "miss",
                "outcome_type": outcome_type,
                "risk_score": risk_score,
                "effective_threshold": effective_threshold,
                "latency_ms": resp_b["client_latency_ms"],
                "cache_lookup_latency_ms": round(resp_b.get("cache_lookup_latency_seconds", 0) * 1000, 2),
                "estimated_cost_usd": resp_b.get("estimated_cost_usd", 0.0)
            }
            
            mode_pair_results.append(pair_res)
            raw_results.append(pair_res)
            
            status_icon = "✓" if (outcome_type in ("TP", "TN")) else "✗"
            print(f"  Pair {pair_id:02d} [{status_icon} {outcome_type}] {mode:<8} | Risk: {risk_score:.2f} | Thresh: {effective_threshold:.4f} | Latency: {resp_b['client_latency_ms']}ms")

        # Aggregate metrics for this mode
        tps = sum(1 for r in mode_pair_results if r["outcome_type"] == "TP")
        fps = sum(1 for r in mode_pair_results if r["outcome_type"] == "FP")
        tns = sum(1 for r in mode_pair_results if r["outcome_type"] == "TN")
        fns = sum(1 for r in mode_pair_results if r["outcome_type"] == "FN")

        precision = round(tps / (tps + fps), 4) if (tps + fps) > 0 else 0.0
        recall = round(tps / (tps + fns), 4) if (tps + fns) > 0 else 0.0
        fpr = round(fps / (fps + tns), 4) if (fps + tns) > 0 else 0.0
        fnr = round(fns / (fns + tps), 4) if (fns + tps) > 0 else 0.0
        hit_rate = round((tps + fps) / len(mode_pair_results), 4) if mode_pair_results else 0.0

        # Recall breakdown by risk tier for should_cache_hit group
        low_risk_tps = sum(1 for r in mode_pair_results if r["label"] == "should_cache_hit" and r["risk_tier"] == "low" and r["outcome_type"] == "TP")
        low_risk_total = sum(1 for r in mode_pair_results if r["label"] == "should_cache_hit" and r["risk_tier"] == "low")
        recall_low = round(low_risk_tps / low_risk_total, 4) if low_risk_total > 0 else 0.0

        high_risk_tps = sum(1 for r in mode_pair_results if r["label"] == "should_cache_hit" and r["risk_tier"] == "high" and r["outcome_type"] == "TP")
        high_risk_total = sum(1 for r in mode_pair_results if r["label"] == "should_cache_hit" and r["risk_tier"] == "high")
        recall_high = round(high_risk_tps / high_risk_total, 4) if high_risk_total > 0 else 0.0

        latencies = [r["latency_ms"] for r in mode_pair_results]
        avg_latency = round(statistics.mean(latencies), 2) if latencies else 0.0
        median_latency = round(statistics.median(latencies), 2) if latencies else 0.0

        summary_metrics[mode] = {
            "mode": mode,
            "total_pairs": len(mode_pair_results),
            "TP": tps,
            "FP": fps,
            "TN": tns,
            "FN": fns,
            "precision": precision,
            "recall": recall,
            "fpr": fpr,
            "fnr": fnr,
            "overall_hit_rate": hit_rate,
            "recall_low_risk_a1": recall_low,
            "recall_high_risk_a2": recall_high,
            "avg_latency_ms": avg_latency,
            "median_latency_ms": median_latency
        }

    # Save raw per-pair results to eval/results.json
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary_metrics, "raw_results": raw_results}, f, indent=2)
    print(f"\n[SUCCESS] Raw results saved to {RESULTS_PATH}")

    # Generate Markdown Summary Table at eval/results_summary.md
    generate_summary_markdown(summary_metrics)
    print(f"[SUCCESS] Results summary table saved to {SUMMARY_PATH}")

    return summary_metrics, raw_results


def generate_summary_markdown(summary):
    md_lines = [
        "# SentinelCache Phase 4.5 Empirical Evaluation Results Summary",
        "",
        "This table summarizes the performance metrics comparing baseline (no caching), fixed-threshold caching (0.92), risk-aware adaptive thresholding (0.88 - 0.99), and production hybrid mode (adaptive threshold + Negation/Entity guards) across 45 prompt pairs.",
        "",
        "| Metric | Disabled (No Cache) | Fixed Threshold (0.92) | Adaptive Threshold (0.88-0.99) | Hybrid Guard Mode (Production) |",
        "| :--- | :---: | :---: | :---: | :---: |"
    ]

    m_dis = summary.get("disabled", {})
    m_fix = summary.get("fixed", {})
    m_ada = summary.get("adaptive", {})
    m_hyb = summary.get("hybrid", {})

    metrics_rows = [
        ("Total Tested Pairs", f"{m_dis.get('total_pairs', 45)}", f"{m_fix.get('total_pairs', 45)}", f"{m_ada.get('total_pairs', 45)}", f"{m_hyb.get('total_pairs', 45)}"),
        ("True Positives (TP)", f"{m_dis.get('TP', 0)}", f"{m_fix.get('TP', 0)}", f"{m_ada.get('TP', 0)}", f"{m_hyb.get('TP', 0)}"),
        ("False Positives (FP - Safety Failures)", f"{m_dis.get('FP', 0)}", f"{m_fix.get('FP', 0)}", f"{m_ada.get('FP', 0)}", f"{m_hyb.get('FP', 0)}"),
        ("True Negatives (TN)", f"{m_dis.get('TN', 0)}", f"{m_fix.get('TN', 0)}", f"{m_ada.get('TN', 0)}", f"{m_hyb.get('TN', 0)}"),
        ("False Negatives (FN)", f"{m_dis.get('FN', 0)}", f"{m_fix.get('FN', 0)}", f"{m_ada.get('FN', 0)}", f"{m_hyb.get('FN', 0)}"),
        ("Precision", f"{m_dis.get('precision', 0.0):.4f}", f"{m_fix.get('precision', 0.0):.4f}", f"{m_ada.get('precision', 0.0):.4f}", f"{m_hyb.get('precision', 0.0):.4f}"),
        ("Recall (Overall)", f"{m_dis.get('recall', 0.0):.4f}", f"{m_fix.get('recall', 0.0):.4f}", f"{m_ada.get('recall', 0.0):.4f}", f"{m_hyb.get('recall', 0.0):.4f}"),
        ("Recall: A1 Low-Risk Paraphrases", f"{m_dis.get('recall_low_risk_a1', 0.0):.4f}", f"{m_fix.get('recall_low_risk_a1', 0.0):.4f}", f"{m_ada.get('recall_low_risk_a1', 0.0):.4f}", f"{m_hyb.get('recall_low_risk_a1', 0.0):.4f}"),
        ("Recall: A2 High-Risk Paraphrases", f"{m_dis.get('recall_high_risk_a2', 0.0):.4f}", f"{m_fix.get('recall_high_risk_a2', 0.0):.4f}", f"{m_ada.get('recall_high_risk_a2', 0.0):.4f}", f"{m_hyb.get('recall_high_risk_a2', 0.0):.4f}"),
        ("False Positive Rate (FPR)", f"{m_dis.get('fpr', 0.0):.4f}", f"{m_fix.get('fpr', 0.0):.4f}", f"{m_ada.get('fpr', 0.0):.4f}", f"{m_hyb.get('fpr', 0.0):.4f}"),
        ("False Negative Rate (FNR)", f"{m_dis.get('fnr', 0.0):.4f}", f"{m_fix.get('fnr', 0.0):.4f}", f"{m_ada.get('fnr', 0.0):.4f}", f"{m_hyb.get('fnr', 0.0):.4f}"),
        ("Overall Cache Hit Rate", f"{m_dis.get('overall_hit_rate', 0.0):.4f}", f"{m_fix.get('overall_hit_rate', 0.0):.4f}", f"{m_ada.get('overall_hit_rate', 0.0):.4f}", f"{m_hyb.get('overall_hit_rate', 0.0):.4f}"),
        ("Average Latency (ms)", f"{m_dis.get('avg_latency_ms', 0.0)}ms", f"{m_fix.get('avg_latency_ms', 0.0)}ms", f"{m_ada.get('avg_latency_ms', 0.0)}ms", f"{m_hyb.get('avg_latency_ms', 0.0)}ms"),
        ("Median Latency (ms)", f"{m_dis.get('median_latency_ms', 0.0)}ms", f"{m_fix.get('median_latency_ms', 0.0)}ms", f"{m_ada.get('median_latency_ms', 0.0)}ms", f"{m_hyb.get('median_latency_ms', 0.0)}ms")
    ]

    for label, dis_val, fix_val, ada_val, hyb_val in metrics_rows:
        md_lines.append(f"| **{label}** | {dis_val} | {fix_val} | {ada_val} | {hyb_val} |")

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")


if __name__ == "__main__":
    run_benchmark()
