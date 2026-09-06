import os
import time
import logging
from typing import Dict, Any, Tuple
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from embedding.embedder import EmbeddingModel
from gateway.cache import CacheClient, map_risk_to_threshold, FIXED_THRESHOLD
from routing.risk_classifier import classify_risk
from routing.provider_registry import get_healthy_providers, PROVIDERS
from routing.router import route_request

# Load environment variables
load_dotenv()

# Logger setup
logger = logging.getLogger("sentinelcache.gateway")
logging.basicConfig(level=logging.INFO)

# Global model and cache client instances
embedder: EmbeddingModel = None
cache_client: CacheClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to initialize embedding model and cache client on startup."""
    global embedder, cache_client
    logger.info("Initializing SentinelCache gateway resources...")

    embedder = EmbeddingModel()
    cache_client = CacheClient()

    try:
        cache_client.create_collection()
    except Exception as exc:
        logger.warning(f"Qdrant collection initialization warning: {exc}. Gateway will run in passthrough mode.")

    yield

    logger.info("Shutting down SentinelCache gateway resources...")


app = FastAPI(
    title="SentinelCache API Gateway",
    description="Cloud-native AI API gateway with complexity-aware semantic caching & dynamic multi-provider routing",
    version="0.4.0",
    lifespan=lifespan
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text to pass to the LLM", min_length=1)


class RiskAssessment(BaseModel):
    risk_score: float = Field(..., description="Calculated prompt risk score between 0.0 and 1.0")
    matched_signals: list[str] = Field(..., description="Rule-based heuristic signals matched for intent classification")
    effective_threshold: float = Field(..., description="Adaptive similarity threshold mapped from risk score")


class RoutingDecision(BaseModel):
    provider: str = Field(..., description="Selected LLM provider name")
    model: str = Field(..., description="Selected LLM model ID")
    tier: str = Field(..., description="Routing tier ('fast_cheap' or 'capable_expensive')")
    reasoning: str = Field(..., description="Explanation for routing selection and fallback path")


class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM generated or cached response text")
    latency: float = Field(..., description="Full round-trip request latency in seconds")
    source: str = Field(..., description="Origin of response ('llm' or 'cache')")
    cache_lookup_latency_seconds: float = Field(..., description="Overhead latency for embedding & Qdrant vector lookup in seconds")
    risk_assessment: RiskAssessment = Field(..., description="Prompt risk classification and adaptive threshold mapping details")
    routing_decision: RoutingDecision = Field(..., description="Multi-provider routing selection & fallback details")
    estimated_cost_usd: float = Field(..., description="Estimated API request cost in USD")


@app.get("/")
async def root():
    """Health check & status endpoint."""
    return {
        "status": "ok",
        "service": "SentinelCache Gateway",
        "version": "0.4.0",
        "default_fixed_threshold": FIXED_THRESHOLD
    }


async def call_provider(provider_config: Dict[str, Any], prompt: str) -> Tuple[str, int, int]:
    """
    Generic OpenAI-compatible HTTP dispatch helper function.

    :param provider_config: Provider dictionary from registry
    :param prompt: User prompt text
    :return: Tuple of (response_text, prompt_tokens, completion_tokens)
    """
    load_dotenv(override=True)
    env_var = provider_config["api_key_env_var"]
    api_key = os.getenv(env_var, "").strip()

    if not api_key or api_key.startswith("your_"):
        raise ValueError(f"API key variable '{env_var}' for provider '{provider_config['name']}' is not configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": provider_config["model_name"],
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(provider_config["api_base_url"], headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()

    response_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
    completion_tokens = usage.get("completion_tokens", len(response_text) // 4)

    return response_text, prompt_tokens, completion_tokens


@app.post(
    "/v1/chat/completions",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send prompt with adaptive risk assessment, semantic cache lookup, dynamic provider routing, and automated fallback"
)
async def chat_completions(request: ChatRequest):
    """
    Handles prompt completion requests:
    1. Classifies prompt risk score & mapped adaptive similarity threshold.
    2. Performs vector cache lookup in Qdrant; if hit, returns cached response instantly ($0 cost).
    3. If cache miss, routes request dynamically to fast_cheap or capable_expensive LLM provider.
    4. Executes fallback resilience if primary provider API call fails.
    5. Calculates estimated USD cost and returns complete response telemetry.
    """
    total_start_time = time.perf_counter()

    # ----------------------------------------------------
    # Step 1: Prompt Risk & Intent Classification
    # ----------------------------------------------------
    risk_info = classify_risk(request.prompt)
    risk_score = risk_info["risk_score"]
    effective_threshold = map_risk_to_threshold(risk_score)

    risk_assessment_obj = RiskAssessment(
        risk_score=risk_score,
        matched_signals=risk_info["matched_signals"],
        effective_threshold=effective_threshold
    )

    # ----------------------------------------------------
    # Step 2: Dynamic Multi-Provider Route Selection
    # ----------------------------------------------------
    route_info = route_request(risk_score, request.prompt)

    # ----------------------------------------------------
    # Step 3: Semantic Vector Cache Lookup
    # ----------------------------------------------------
    cache_start_time = time.perf_counter()
    cached_hit = None
    prompt_embedding = None

    if embedder and cache_client:
        try:
            prompt_embedding = embedder.embed(request.prompt)
            cached_hit = cache_client.lookup(prompt_embedding, risk_score=risk_score)
        except Exception as exc:
            logger.warning(f"Cache lookup failed: {exc}. Proceeding to LLM provider.")

    cache_lookup_latency = round(time.perf_counter() - cache_start_time, 4)

    # ----------------------------------------------------
    # Step 4: Handle Cache HIT
    # ----------------------------------------------------
    if cached_hit is not None:
        total_latency = round(time.perf_counter() - total_start_time, 4)

        routing_decision_obj = RoutingDecision(
            provider=route_info["provider"],
            model=route_info["model"],
            tier=route_info["tier"],
            reasoning=f"{route_info['reasoning']} (Served from cache: LLM call bypassed)."
        )

        return ChatResponse(
            response=cached_hit["response"],
            latency=total_latency,
            source="cache",
            cache_lookup_latency_seconds=cache_lookup_latency,
            risk_assessment=risk_assessment_obj,
            routing_decision=routing_decision_obj,
            estimated_cost_usd=0.0
        )

    # ----------------------------------------------------
    # Step 5: Handle Cache MISS -> LLM Provider Dispatch & Fallback
    # ----------------------------------------------------
    # Candidate sequence: selected primary provider first, followed by remaining providers
    candidate_configs = [route_info["selected_config"]]
    for p in PROVIDERS:
        if p["name"] != route_info["selected_config"]["name"]:
            candidate_configs.append(p)

    last_exception = None
    response_text = None
    prompt_tokens = 0
    completion_tokens = 0
    successful_provider = None

    for idx, provider_config in enumerate(candidate_configs):
        try:
            logger.info(f"Attempting API call to provider '{provider_config['name']}' ({provider_config['model_name']})...")
            response_text, prompt_tokens, completion_tokens = await call_provider(provider_config, request.prompt)
            successful_provider = provider_config
            if idx > 0:
                logger.info(f"Fallback SUCCESS: Provider '{provider_config['name']}' responded successfully after primary provider failure.")
            break
        except Exception as exc:
            last_exception = exc
            logger.warning(f"Provider '{provider_config['name']}' failed: {exc}. Trying next candidate...")

    if not response_text or not successful_provider:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All candidate LLM providers failed. Last error: {str(last_exception)}"
        )

    # Store response in Qdrant prompt_cache for future cache hits
    if cache_client and prompt_embedding is not None:
        try:
            cache_client.store(request.prompt, prompt_embedding, response_text)
        except Exception as exc:
            logger.warning(f"Failed to store entry in cache: {exc}")

    # Calculate estimated USD cost
    cost_input = (prompt_tokens / 1000.0) * successful_provider["cost_per_1k_input_tokens"]
    cost_output = (completion_tokens / 1000.0) * successful_provider["cost_per_1k_output_tokens"]
    estimated_cost = round(cost_input + cost_output, 8)

    total_latency = round(time.perf_counter() - total_start_time, 4)

    final_reasoning = route_info["reasoning"]
    if successful_provider["name"] != route_info["provider"]:
        final_reasoning += f" Primary provider '{route_info['provider']}' failed. Successfully fell back to '{successful_provider['name']}'."

    routing_decision_obj = RoutingDecision(
        provider=successful_provider["name"],
        model=successful_provider["model_name"],
        tier=successful_provider["priority_tier"],
        reasoning=final_reasoning
    )

    return ChatResponse(
        response=response_text,
        latency=total_latency,
        source="llm",
        cache_lookup_latency_seconds=cache_lookup_latency,
        risk_assessment=risk_assessment_obj,
        routing_decision=routing_decision_obj,
        estimated_cost_usd=estimated_cost
    )
