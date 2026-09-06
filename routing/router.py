"""
Dynamic Multi-Provider Router for SentinelCache.

Selects the optimal LLM provider tier based on prompt risk score and health status.

Note: Reusing risk_score as a proxy for task complexity is a v1 heuristic.
A dedicated task complexity classifier (trained on prompt length, code snippets,
and reasoning depth separate from risk) is a documented future improvement.
"""

import logging
from typing import Dict, Any
from routing.provider_registry import get_healthy_providers, PROVIDERS

logger = logging.getLogger("sentinelcache.routing")


def route_request(risk_score: float, prompt: str) -> Dict[str, Any]:
    """
    Routes a request to the appropriate LLM provider tier based on risk score and health.

    :param risk_score: Prompt risk score in [0.0, 1.0] from risk_classifier
    :param prompt: Raw input user prompt text
    :return: dict with 'provider', 'model', 'tier', 'reasoning', and 'candidate_providers'
    """
    healthy_providers = get_healthy_providers()

    # Determine target tier based on risk score cutoff
    if risk_score >= 0.5:
        target_tier = "capable_expensive"
        cutoff_reasoning = f"Risk score {risk_score:.2f} >= 0.50 cutoff -> Selected capable_expensive tier."
    else:
        target_tier = "fast_cheap"
        cutoff_reasoning = f"Risk score {risk_score:.2f} < 0.50 cutoff -> Selected fast_cheap tier."

    # Filter healthy providers in the target tier
    tier_candidates = [p for p in healthy_providers if p["priority_tier"] == target_tier]

    # Fallback to alternative tier if no healthy providers exist in target tier
    if not tier_candidates:
        alt_candidates = [p for p in healthy_providers if p["priority_tier"] != target_tier]
        if alt_candidates:
            selected_provider = alt_candidates[0]
            reasoning = f"{cutoff_reasoning} However, no healthy providers were active in '{target_tier}'. Falling back to alternative healthy provider '{selected_provider['name']}' ({selected_provider['priority_tier']})."
            candidate_list = alt_candidates
        else:
            # Ultimate fallback: return registry default (Groq) with warning
            selected_provider = PROVIDERS[0]
            reasoning = f"{cutoff_reasoning} No healthy API keys detected. Falling back to default provider '{selected_provider['name']}'."
            candidate_list = PROVIDERS
    else:
        selected_provider = tier_candidates[0]
        reasoning = f"{cutoff_reasoning} Selected healthy provider '{selected_provider['name']}' ({selected_provider['model_name']})."
        candidate_list = tier_candidates

    return {
        "provider": selected_provider["name"],
        "model": selected_provider["model_name"],
        "tier": selected_provider["priority_tier"],
        "reasoning": reasoning,
        "selected_config": selected_provider,
        "candidate_providers": candidate_list
    }
