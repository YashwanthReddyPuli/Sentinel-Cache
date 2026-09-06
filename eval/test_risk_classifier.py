"""
Evaluation Suite for SentinelCache Risk Classifier (Phase 2).

Tests the rule-based prompt risk classifier and threshold mapping function
across 10+ representative prompt test cases.
"""

import sys
import os

# Ensure repository root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routing.risk_classifier import classify_risk
from gateway.cache import map_risk_to_threshold

TEST_CASES = [
    # ----------------------------------------------------
    # Category 1: Clear High-Risk Action Prompts (Target Risk >= 0.70)
    # ----------------------------------------------------
    {
        "prompt": "Cancel my subscription immediately.",
        "category": "High Risk Action",
        "expected_min_risk": 0.70,
        "expected_signal_type": "high_risk_verb"
    },
    {
        "prompt": "Delete user account and purge data.",
        "category": "High Risk Action",
        "expected_min_risk": 0.70,
        "expected_signal_type": "high_risk_verb"
    },
    {
        "prompt": "Downgrade my subscription plan to basic.",
        "category": "High Risk Action",
        "expected_min_risk": 0.70,
        "expected_signal_type": "high_risk_verb"
    },
    {
        "prompt": "Refund my last credit card charge.",
        "category": "High Risk Action",
        "expected_min_risk": 0.70,
        "expected_signal_type": "high_risk_verb"
    },

    # ----------------------------------------------------
    # Category 2: Negation Edge Cases (Target Risk >= 0.85)
    # ----------------------------------------------------
    {
        "prompt": "Don't cancel my subscription under any circumstances.",
        "category": "High Risk Negation Edge Case",
        "expected_min_risk": 0.85,
        "expected_signal_type": "negation_word"
    },
    {
        "prompt": "Do not delete my user files.",
        "category": "High Risk Negation Edge Case",
        "expected_min_risk": 0.85,
        "expected_signal_type": "negation_word"
    },

    # ----------------------------------------------------
    # Category 3: Clear Low-Risk Informational Queries (Target Risk <= 0.30)
    # ----------------------------------------------------
    {
        "prompt": "What is semantic caching?",
        "category": "Low Risk Informational",
        "expected_max_risk": 0.30,
        "expected_signal_type": "informational_marker"
    },
    {
        "prompt": "Explain quantum computing in simple terms.",
        "category": "Low Risk Informational",
        "expected_max_risk": 0.30,
        "expected_signal_type": "informational_marker"
    },
    {
        "prompt": "Define artificial intelligence and list key differences between machine learning and deep learning.",
        "category": "Low Risk Informational",
        "expected_max_risk": 0.30,
        "expected_signal_type": "informational_marker"
    },

    # ----------------------------------------------------
    # Category 4: Ambiguous / Default Bucket Prompts (Target Risk == 0.50)
    # ----------------------------------------------------
    {
        "prompt": "Today is a pleasant Sunday morning.",
        "category": "Default Bucket",
        "expected_risk": 0.50,
        "expected_signal_type": "default_heuristic"
    },
    {
        "prompt": "The quick brown fox jumps over the lazy dog.",
        "category": "Default Bucket",
        "expected_risk": 0.50,
        "expected_signal_type": "default_heuristic"
    }
]


def run_evaluation():
    print("=" * 80)
    print("SENTINELCACHE PHASE 2: RISK CLASSIFIER EVALUATION SUITE")
    print("=" * 80)
    print(f"{'Category':<28} | {'Risk':<5} | {'Threshold':<9} | {'Prompt':<30}")
    print("-" * 80)

    passed_count = 0

    for i, test in enumerate(TEST_CASES, 1):
        prompt = test["prompt"]
        category = test["category"]
        result = classify_risk(prompt)
        risk_score = result["risk_score"]
        signals = result["matched_signals"]
        mapped_threshold = map_risk_to_threshold(risk_score)

        # Validation logic
        passed = True
        if "expected_min_risk" in test and risk_score < test["expected_min_risk"]:
            passed = False
        if "expected_max_risk" in test and risk_score > test["expected_max_risk"]:
            passed = False
        if "expected_risk" in test and abs(risk_score - test["expected_risk"]) > 0.01:
            passed = False
        if "expected_signal_type" in test and not any(test["expected_signal_type"] in sig for sig in signals):
            passed = False

        status_str = "PASS" if passed else "FAIL"
        if passed:
            passed_count += 1

        print(f"[{status_str}] {category:<23} | {risk_score:<5.2f} | {mapped_threshold:<9.4f} | \"{prompt[:28]}\"")
        print(f"      Matched Signals: {signals}")

    print("-" * 80)
    print(f"TOTAL RESULT: {passed_count}/{len(TEST_CASES)} tests passed.")
    print("=" * 80)
    return passed_count == len(TEST_CASES)


if __name__ == "__main__":
    success = run_evaluation()
    sys.exit(0 if success else 1)
