import os
import json
import numpy as np
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "benchmark_dataset.json")
COMPARISON_JSON_PATH = os.path.join(BASE_DIR, "embedding_model_comparison.json")
OVERLAP_PNG_PATH = os.path.join(BASE_DIR, "similarity_distribution_overlap.png")
MODEL_COMP_PNG_PATH = os.path.join(BASE_DIR, "embedding_model_comparison.png")

def load_dataset():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def compute_model_similarities(model_name: str, dataset: list) -> dict:
    print(f"\nLoading embedding model '{model_name}'...")
    model = SentenceTransformer(model_name)
    
    cat_a_scores = []
    cat_b_scores = []
    pair_details = []
    
    for item in dataset:
        v1 = model.encode(item["prompt_a"], convert_to_numpy=True)
        v2 = model.encode(item["prompt_b"], convert_to_numpy=True)
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        
        detail = {
            "id": item["id"],
            "category": item["category"],
            "label": item["label"],
            "risk_tier": item["risk_tier"],
            "prompt_a": item["prompt_a"],
            "prompt_b": item["prompt_b"],
            "cosine_similarity": sim
        }
        pair_details.append(detail)
        
        if item["label"] == "should_cache_hit":
            cat_a_scores.append(sim)
        else:
            cat_b_scores.append(sim)
            
    max_b = max(cat_b_scores)
    min_a = min(cat_a_scores)
    a_below_max_b = sum(1 for s in cat_a_scores if s < max_b)
    
    return {
        "model_name": model_name,
        "cat_a_scores": cat_a_scores,
        "cat_b_scores": cat_b_scores,
        "max_b_score": max_b,
        "min_a_score": min_a,
        "a_below_max_b_count": a_below_max_b,
        "pair_details": pair_details
    }

def generate_overlap_chart(minilm_data: dict):
    plt.figure(figsize=(10, 6))
    
    cat_a = minilm_data["cat_a_scores"]
    cat_b = minilm_data["cat_b_scores"]
    
    # Strip plot / scatter
    y_a = np.ones_like(cat_a) * 1.5 + np.random.uniform(-0.1, 0.1, len(cat_a))
    y_b = np.ones_like(cat_b) * 0.5 + np.random.uniform(-0.1, 0.1, len(cat_b))
    
    plt.scatter(cat_a, y_a, color="#2ecc71", alpha=0.8, s=60, label="Category A (True Paraphrase: Should Hit, n=25)")
    plt.scatter(cat_b, y_b, color="#e74c3c", alpha=0.8, s=60, label="Category B (Intent-Distinct: Should NOT Hit, n=20)")
    
    # Threshold lines
    plt.axvline(x=0.92, color="#3498db", linestyle="--", linewidth=2, label="Fixed Threshold (0.92)")
    plt.axvspan(0.88, 0.99, color="#9b59b6", alpha=0.15, label="Adaptive Threshold Range (0.88 - 0.99)")
    
    plt.xlim(0.45, 1.0)
    plt.ylim(0.0, 2.0)
    plt.yticks([0.5, 1.5], ["Category B\n(Intent-Distinct)", "Category A\n(True Paraphrases)"])
    plt.xlabel("Cosine Similarity Score (all-MiniLM-L6-v2)", fontsize=12)
    plt.title("Cosine Similarity Distribution Overlap: Category A vs Category B", fontsize=14, fontweight="bold")
    plt.legend(loc="upper left")
    plt.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    plt.savefig(OVERLAP_PNG_PATH, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved single overlap plot to {OVERLAP_PNG_PATH}")

def generate_side_by_side_comparison_chart(minilm_data: dict, mpnet_data: dict):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6), sharey=True)
    
    for ax, data, title in [
        (ax1, minilm_data, "all-MiniLM-L6-v2 (22M Params, 384 Dim)"),
        (ax2, mpnet_data, "all-mpnet-base-v2 (110M Params, 768 Dim)")
    ]:
        cat_a = data["cat_a_scores"]
        cat_b = data["cat_b_scores"]
        
        y_a = np.ones_like(cat_a) * 1.5 + np.random.uniform(-0.1, 0.1, len(cat_a))
        y_b = np.ones_like(cat_b) * 0.5 + np.random.uniform(-0.1, 0.1, len(cat_b))
        
        ax.scatter(cat_a, y_a, color="#2ecc71", alpha=0.8, s=60, label="Category A (True Paraphrases)")
        ax.scatter(cat_b, y_b, color="#e74c3c", alpha=0.8, s=60, label="Category B (Intent-Distinct)")
        
        ax.axvline(x=0.92, color="#3498db", linestyle="--", linewidth=2, label="Fixed Thresh (0.92)")
        ax.axvspan(0.88, 0.99, color="#9b59b6", alpha=0.15, label="Adaptive Range (0.88-0.99)")
        
        ax.set_xlim(0.45, 1.0)
        ax.set_ylim(0.0, 2.0)
        ax.set_xlabel("Cosine Similarity Score", fontsize=11)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, linestyle=":", alpha=0.6)
        
    ax1.set_yticks([0.5, 1.5])
    ax1.set_yticklabels(["Category B\n(Intent-Distinct)", "Category A\n(True Paraphrases)"])
    
    plt.suptitle("Embedding Model Category Separation Comparison: MiniLM vs mpnet-base", fontsize=15, fontweight="bold")
    plt.tight_layout()
    plt.savefig(MODEL_COMP_PNG_PATH, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved side-by-side comparison plot to {MODEL_COMP_PNG_PATH}")

def main():
    dataset = load_dataset()
    
    minilm_res = compute_model_similarities("sentence-transformers/all-MiniLM-L6-v2", dataset)
    mpnet_res = compute_model_similarities("sentence-transformers/all-mpnet-base-v2", dataset)
    
    comp_json = {
        "all-MiniLM-L6-v2": {
            "max_b_score": minilm_res["max_b_score"],
            "min_a_score": minilm_res["min_a_score"],
            "a_below_max_b_count": minilm_res["a_below_max_b_count"],
            "pair_details": minilm_res["pair_details"]
        },
        "all-mpnet-base-v2": {
            "max_b_score": mpnet_res["max_b_score"],
            "min_a_score": mpnet_res["min_a_score"],
            "a_below_max_b_count": mpnet_res["a_below_max_b_count"],
            "pair_details": mpnet_res["pair_details"]
        }
    }
    
    with open(COMPARISON_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(comp_json, f, indent=2)
    print(f"[SUCCESS] Saved comparison results to {COMPARISON_JSON_PATH}")
    
    generate_overlap_chart(minilm_res)
    generate_side_by_side_comparison_chart(minilm_res, mpnet_res)

if __name__ == "__main__":
    main()
