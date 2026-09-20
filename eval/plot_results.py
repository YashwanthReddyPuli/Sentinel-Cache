"""
Plotting Script for SentinelCache Benchmark Results (Phase 4).

Generates three figures using matplotlib:
1. eval/precision_recall_comparison.png: Grouped bar chart (Precision, Recall, FPR, FNR) comparing Fixed vs Adaptive.
2. eval/recall_by_risk_tier.png: Bar chart showing Recall (A1 Low-Risk vs A2 High-Risk) for Adaptive Mode.
3. eval/latency_comparison.png: Bar chart comparing Average Latency across Disabled, Fixed, and Adaptive modes.
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(BASE_DIR, "results.json")

FIG1_PATH = os.path.join(BASE_DIR, "precision_recall_comparison.png")
FIG2_PATH = os.path.join(BASE_DIR, "recall_by_risk_tier.png")
FIG3_PATH = os.path.join(BASE_DIR, "latency_comparison.png")


def load_summary():
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["summary"]


def plot_precision_recall_comparison(summary):
    fixed = summary["fixed"]
    adaptive = summary["adaptive"]

    metrics = ["Precision", "Recall", "False Positive Rate", "False Negative Rate"]
    fixed_vals = [fixed["precision"], fixed["recall"], fixed["fpr"], fixed["fnr"]]
    adaptive_vals = [adaptive["precision"], adaptive["recall"], adaptive["fpr"], adaptive["fnr"]]

    x = np.arange(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))

    rects1 = ax.bar(x - width/2, fixed_vals, width, label="Fixed Threshold (0.92)", color="#e74c3c")
    rects2 = ax.bar(x + width/2, adaptive_vals, width, label="Adaptive Threshold (0.88-0.99)", color="#2ecc71")

    ax.set_ylabel("Score / Rate", fontsize=12, fontweight="bold")
    ax.set_title("SentinelCache Evaluation: Fixed vs Adaptive Threshold Performance", fontsize=14, fontweight="bold", pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11, fontweight="bold")
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=11)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.2%}",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=10, fontweight="bold")

    autolabel(rects1)
    autolabel(rects2)

    fig.tight_layout()
    plt.savefig(FIG1_PATH, dpi=300)
    plt.close()
    print(f"Generated Figure 1: {FIG1_PATH}")


def plot_recall_by_risk_tier(summary):
    adaptive = summary["adaptive"]
    
    tiers = ["A1: Low-Risk Paraphrases\n(Risk ~0.10-0.20)", "A2: High-Risk Paraphrases\n(Risk ~0.70+)"]
    recalls = [adaptive["recall_low_risk_a1"], adaptive["recall_high_risk_a2"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(tiers, recalls, color=["#3498db", "#f39c12"], width=0.45)

    ax.set_ylabel("Recall Rate", fontsize=12, fontweight="bold")
    ax.set_title("Adaptive Configuration: Recall Breakdown by Prompt Risk Tier", fontsize=13, fontweight="bold", pad=15)
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.2%}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=11, fontweight="bold")

    fig.tight_layout()
    plt.savefig(FIG2_PATH, dpi=300)
    plt.close()
    print(f"Generated Figure 2: {FIG2_PATH}")


def plot_latency_comparison(summary):
    modes = ["Disabled\n(Pure LLM)", "Fixed Threshold\n(0.92)", "Adaptive Threshold\n(0.88-0.99)"]
    latencies = [
        summary["disabled"]["avg_latency_ms"],
        summary["fixed"]["avg_latency_ms"],
        summary["adaptive"]["avg_latency_ms"]
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(modes, latencies, color=["#95a5a6", "#e74c3c", "#2ecc71"], width=0.45)

    ax.set_ylabel("Average Latency (ms)", fontsize=12, fontweight="bold")
    ax.set_title("Average Client Latency Comparison Across Gateway Modes", fontsize=13, fontweight="bold", pad=15)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.1f} ms",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=11, fontweight="bold")

    fig.tight_layout()
    plt.savefig(FIG3_PATH, dpi=300)
    plt.close()
    print(f"Generated Figure 3: {FIG3_PATH}")


def main():
    summary = load_summary()
    plot_precision_recall_comparison(summary)
    plot_recall_by_risk_tier(summary)
    plot_latency_comparison(summary)
    print("\nAll 3 chart figures generated successfully!")


if __name__ == "__main__":
    main()
