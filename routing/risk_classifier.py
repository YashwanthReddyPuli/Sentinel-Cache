"""
Rule-Based Prompt Risk & Intent Classifier for SentinelCache (v1 Heuristic).

Calculates a prompt risk score between 0.0 (low risk / safe to cache loosely)
and 1.0 (high risk / operational / must match strictly).

Future Improvement Note:
This rule-based heuristic classifier is a v1 baseline implementation.
A zero-shot classification model (e.g., DeBERTa-v3 or BART-large-MNLI) or fine-tuned
intent classifier is a documented future enhancement to replace rule matching.
"""

import re

HIGH_RISK_VERBS = [
    "cancel", "delete", "downgrade", "upgrade", "refund",
    "unsubscribe", "terminate", "close", "remove", "revoke",
    "transfer", "charge"
]

LOW_RISK_MARKERS = [
    "difference between", "when was", "who is",
    "what", "how", "explain", "define", "who", "when", "where", "which", "why"
]

NEGATION_WORDS = [
    "not", "don't", "dont", "never", "no", "without",
    "shouldn't", "shouldnt", "can't", "cant", "cannot", "won't", "wont"
]


def classify_risk(prompt: str) -> dict:
    """
    Classifies prompt risk and intent safety.

    :param prompt: Raw input user prompt text
    :return: dict with 'risk_score' (float in [0.0, 1.0]) and 'matched_signals' (list[str])
    """
    if not prompt or not prompt.strip():
        return {
            "risk_score": 0.5,
            "matched_signals": ["empty_prompt_default"]
        }

    clean_prompt = prompt.lower().strip()
    words = re.findall(r'\b\w+\b', clean_prompt)
    word_count = len(words)
    matched_signals = []

    # ----------------------------------------------------
    # Signal 1: High-Risk Action Verbs
    # ----------------------------------------------------
    matched_verbs = [verb for verb in HIGH_RISK_VERBS if re.search(r'\b' + re.escape(verb) + r'\b', clean_prompt)]

    if matched_verbs:
        for verb in matched_verbs:
            matched_signals.append(f"high_risk_verb:{verb}")
        
        risk_score = 0.70

        # Check for negation words which significantly alter intent
        matched_negations = [neg for neg in NEGATION_WORDS if re.search(r'\b' + re.escape(neg) + r'\b', clean_prompt)]
        if matched_negations:
            for neg in matched_negations:
                matched_signals.append(f"negation_word:{neg}")
            risk_score += 0.15

        risk_score = min(1.0, round(risk_score, 2))
        return {
            "risk_score": risk_score,
            "matched_signals": matched_signals
        }

    # ----------------------------------------------------
    # Signal 2: Informational / Safe Queries
    # ----------------------------------------------------
    matched_info_markers = [marker for marker in LOW_RISK_MARKERS if marker in clean_prompt]

    if matched_info_markers:
        for marker in matched_info_markers:
            matched_signals.append(f"informational_marker:{marker}")

        # Length-based scaling: shorter generic questions are lower risk
        if word_count <= 5:
            risk_score = 0.10
        elif word_count <= 15:
            risk_score = 0.20
        else:
            risk_score = 0.30

        return {
            "risk_score": round(risk_score, 2),
            "matched_signals": matched_signals
        }

    # ----------------------------------------------------
    # Signal 3: Default Bucket
    # ----------------------------------------------------
    matched_signals.append("default_heuristic")
    return {
        "risk_score": 0.50,
        "matched_signals": matched_signals
    }
