"""
LLM Provider Registry for SentinelCache.

Config-driven list of providers, per-token pricing metadata, context limits,
and priority tiers ('fast_cheap' vs 'capable_expensive').
"""

import os
from typing import Dict, List, Any

# Provider configurations with real published per-token pricing
PROVIDERS: List[Dict[str, Any]] = [
    {
        "name": "Groq",
        "api_base_url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env_var": "GROQ_API_KEY",
        "model_name": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        "cost_per_1k_input_tokens": 0.00005,   # $0.05 / 1M tokens
        "cost_per_1k_output_tokens": 0.00008,  # $0.08 / 1M tokens
        "max_context_tokens": 128000,
        "priority_tier": "fast_cheap"
    },
    {
        "name": "Groq-Secondary",
        "api_base_url": "https://api.groq.com/openai/v1/chat/completions",
        "api_key_env_var": "GROQ_API_KEY",
        "model_name": "qwen/qwen3.6-27b",
        "cost_per_1k_input_tokens": 0.00006,   # $0.06 / 1M tokens
        "cost_per_1k_output_tokens": 0.00009,  # $0.09 / 1M tokens
        "max_context_tokens": 128000,
        "priority_tier": "fast_cheap"
    },
    {
        "name": "OpenAI",
        "api_base_url": "https://api.openai.com/v1/chat/completions",
        "api_key_env_var": "OPENAI_API_KEY",
        "model_name": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "cost_per_1k_input_tokens": 0.00015,   # $0.15 / 1M tokens
        "cost_per_1k_output_tokens": 0.00060,  # $0.60 / 1M tokens
        "max_context_tokens": 128000,
        "priority_tier": "capable_expensive"
    }
]


def get_healthy_providers() -> List[Dict[str, Any]]:
    """
    Returns a list of active, healthy providers that have a configured API key.

    Note: Real-time active health checks (e.g. tracking rolling HTTP error rates,
    circuit breaking, or response latency monitoring) are a documented future improvement.
    Currently, health is determined by checking if the provider's API key is configured.
    """
    healthy = []
    for p in PROVIDERS:
        api_key = os.getenv(p["api_key_env_var"], "").strip()
        # Mark healthy if API key exists and is not a placeholder
        is_healthy = bool(api_key and not api_key.startswith("your_"))
        
        provider_copy = p.copy()
        provider_copy["healthy"] = is_healthy
        if is_healthy:
            healthy.append(provider_copy)
            
    return healthy
