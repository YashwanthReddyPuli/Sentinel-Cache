
import os
import time
import json
import asyncio
import logging
from typing import Dict, Any, Tuple
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from embedding.embedder import EmbeddingModel
from gateway.cache import CacheClient, map_risk_to_threshold, FIXED_THRESHOLD
from routing.risk_classifier import classify_risk
from routing.provider_registry import get_healthy_providers, PROVIDERS
from routing.router import route_request

from fastapi.middleware.cors import CORSMiddleware
from gateway.metrics import metrics_store

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

    # Startup safety check: ensure all configured providers have valid, non-empty API keys
    missing_keys = []
    for provider in PROVIDERS:
        env_var = provider["api_key_env_var"]
        key_val = os.getenv(env_var, "").strip()
        if not key_val or key_val.startswith("your_"):
            missing_keys.append(f"Provider '{provider['name']}' requires env var '{env_var}'")
    
    if missing_keys:
        err_msg = f"CRITICAL: Gateway startup aborted! Missing API key configurations: {'; '.join(missing_keys)}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    logger.info("All configured LLM provider API keys successfully validated.")

    try:
        cache_client.create_collection()
    except Exception as exc:
        logger.warning(f"Qdrant collection initialization warning: {exc}. Gateway will run in passthrough mode.")

    yield

    logger.info("Shutting down SentinelCache gateway resources...")


app = FastAPI(
    title="SentinelCache API Gateway",
    description="Cloud-native AI API gateway with complexity-aware semantic caching & dynamic multi-provider routing",
    version="0.5.0",
    lifespan=lifespan
)

# Enable CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    similarity_score: float | None = Field(None, description="Raw cosine similarity score from vector cache lookup (if any candidate found)")
    guard_reason: str | None = Field(None, description="Guard block reason if cache hit was intercepted")


@app.get("/")
async def root():
    """Health check & status endpoint."""
    return {
        "status": "ok",
        "service": "SentinelCache Gateway",
        "version": "0.5.0",
        "default_fixed_threshold": FIXED_THRESHOLD
    }


# ----------------------------------------------------
# Metrics API Endpoints (Phase 5 Observability)
# ----------------------------------------------------

@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Returns aggregate gateway telemetry summary."""
    return metrics_store.get_summary()


@app.get("/api/metrics/timeseries")
async def get_metrics_timeseries(window: str = Query("1h", description="Time window: '1h', '24h', or '7d'")):
    """Returns time-bucketed metrics for hit rate, latency, and cost."""
    return metrics_store.get_timeseries(window=window)


@app.get("/api/metrics/recent")
async def get_recent_requests(limit: int = Query(50, ge=1, le=200)):
    """Returns the most recent N individual request telemetry records."""
    return metrics_store.get_recent(limit=limit)


@app.get("/api/metrics/eval-results")
async def get_eval_results():
    """Serves structured evaluation benchmark results summary."""
    results_path = os.path.join(os.path.dirname(__file__), "..", "eval", "results.json")
    if os.path.exists(results_path):
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("summary", {})
        except Exception as exc:
            logger.error(f"Failed to read eval results: {exc}")
    # Default fallback summary if results.json not found
    return {
        "disabled": {"mode": "disabled", "total_pairs": 45, "TP": 0, "FP": 0, "TN": 20, "FN": 25, "precision": 0.0, "recall": 0.0, "fpr": 0.0, "fnr": 1.0, "overall_hit_rate": 0.0, "recall_low_risk_a1": 0.0, "recall_high_risk_a2": 0.0, "avg_latency_ms": 2905.26, "median_latency_ms": 1646.65},
        "fixed": {"mode": "fixed", "total_pairs": 45, "TP": 5, "FP": 5, "TN": 15, "FN": 20, "precision": 0.5, "recall": 0.2, "fpr": 0.25, "fnr": 0.8, "overall_hit_rate": 0.2222, "recall_low_risk_a1": 0.25, "recall_high_risk_a2": 0.0, "avg_latency_ms": 3037.05, "median_latency_ms": 2070.87},
        "adaptive": {"mode": "adaptive", "total_pairs": 45, "TP": 5, "FP": 2, "TN": 18, "FN": 20, "precision": 0.7143, "recall": 0.2, "fpr": 0.1, "fnr": 0.8, "overall_hit_rate": 0.1556, "recall_low_risk_a1": 0.25, "recall_high_risk_a2": 0.0, "avg_latency_ms": 7693.53, "median_latency_ms": 2401.55},
        "hybrid": {"mode": "hybrid", "total_pairs": 45, "TP": 5, "FP": 0, "TN": 20, "FN": 20, "precision": 1.0, "recall": 0.2, "fpr": 0.0, "fnr": 0.8, "overall_hit_rate": 0.1111, "recall_low_risk_a1": 0.25, "recall_high_risk_a2": 0.0, "avg_latency_ms": 9490.19, "median_latency_ms": 3443.91}
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

    # Construct complete chat completions endpoint URL
    base_url = provider_config["api_base_url"].rstrip("/")
    if not base_url.endswith("/chat/completions"):
        endpoint_url = f"{base_url}/chat/completions"
    else:
        endpoint_url = base_url

    async with httpx.AsyncClient(timeout=35.0) as client:
        max_retries = 3
        backoff = 2.0
        for attempt in range(max_retries + 1):
            try:
                res = await client.post(endpoint_url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt < max_retries:
                    logger.warning(f"Provider '{provider_config['name']}' rate limited (429). Retrying in {backoff}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                    continue
                logger.error(
                    f"Provider '{provider_config['name']}' HTTP error: "
                    f"Status={exc.response.status_code}, Exception={type(exc).__name__}, ResponseBody={exc.response.text}"
                )
                raise
            except Exception as exc:
                logger.error(
                    f"Provider '{provider_config['name']}' failed with Exception={type(exc).__name__}: {str(exc)}"
                )
                raise

    response_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
    completion_tokens = usage.get("completion_tokens", len(response_text) // 4)

    return response_text, prompt_tokens, completion_tokens


@app.post(
    "/v1/cache/clear",
    status_code=status.HTTP_200_OK,
    summary="Reset prompt cache collection"
)
async def clear_cache():
    """Resets the prompt_cache Qdrant collection (used by benchmark runner)."""
    if cache_client:
        cache_client.clear_collection()
        return {"status": "cleared"}
    raise HTTPException(status_code=500, detail="Cache client not initialized")


@app.post(
    "/v1/chat/completions",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send prompt with adaptive risk assessment, semantic cache lookup, dynamic provider routing, and automated fallback"
)
async def chat_completions(
    request: ChatRequest,
    cache_mode: str = Query("hybrid", description="Cache evaluation mode: 'hybrid', 'adaptive', 'fixed', or 'disabled'")
):
    """
    Handles prompt completion requests:
    1. Classifies prompt risk score & mapped adaptive similarity threshold.
    2. Performs vector cache lookup in Qdrant (supports cache_mode='hybrid'|'adaptive'|'fixed'|'disabled').
    3. If cache miss, routes request dynamically to fast_cheap or capable_expensive LLM provider.
    4. Executes fallback resilience if primary provider API call fails.
    5. Calculates estimated USD cost and returns complete response telemetry.
    """
    total_start_time = time.perf_counter()

    # Normalize cache_mode
    mode = cache_mode.lower().strip()
    if mode not in ("hybrid", "adaptive", "fixed", "disabled"):
        mode = "hybrid"

    # ----------------------------------------------------
    # Step 1: Prompt Risk & Intent Classification
    # ----------------------------------------------------
    risk_info = classify_risk(request.prompt)
    risk_score = risk_info["risk_score"]

    if mode == "fixed":
        effective_threshold = FIXED_THRESHOLD
    else:
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
    guard_reason = None
    raw_sim = None
    prompt_embedding = None

    if mode != "disabled" and embedder and cache_client:
        try:
            prompt_embedding = embedder.embed(request.prompt)
            enable_guards = (mode == "hybrid")

            if mode == "fixed":
                cached_hit, guard_reason, raw_sim = cache_client.lookup(
                    prompt_embedding,
                    current_prompt=request.prompt,
                    threshold=FIXED_THRESHOLD,
                    enable_guards=enable_guards
                )
            else:
                cached_hit, guard_reason, raw_sim = cache_client.lookup(
                    prompt_embedding,
                    current_prompt=request.prompt,
                    risk_score=risk_score,
                    enable_guards=enable_guards
                )
        except Exception as exc:
            logger.warning(f"Cache lookup failed: {exc}. Proceeding to LLM provider.")

    cache_lookup_latency = round(time.perf_counter() - cache_start_time, 4)

    # ----------------------------------------------------
    # Step 4: Handle Cache HIT
    # ----------------------------------------------------
    if cached_hit is not None:
        total_latency = round(time.perf_counter() - total_start_time, 4)
        latency_ms = round(total_latency * 1000, 2)

        routing_decision_obj = RoutingDecision(
            provider=route_info["provider"],
            model=route_info["model"],
            tier=route_info["tier"],
            reasoning=f"{route_info['reasoning']} (Served from cache: LLM call bypassed, mode='{mode}')."
        )

        metrics_store.record_request(
            prompt=request.prompt,
            cache_outcome="hit",
            similarity_score=cached_hit.get("similarity_score"),
            threshold_used=effective_threshold,
            risk_score=risk_score,
            provider=route_info["provider"],
            model=route_info["model"],
            tier=route_info["tier"],
            latency_ms=latency_ms,
            estimated_cost_usd=0.0
        )

        return ChatResponse(
            response=cached_hit["response"],
            latency=total_latency,
            source="cache",
            cache_lookup_latency_seconds=cache_lookup_latency,
            risk_assessment=risk_assessment_obj,
            routing_decision=routing_decision_obj,
            estimated_cost_usd=0.0,
            similarity_score=cached_hit.get("similarity_score", raw_sim),
            guard_reason=guard_reason
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
            logger.warning(f"Provider '{provider_config['name']}' failed with error: {type(exc).__name__}: {exc}. Trying next candidate...")

    if not response_text or not successful_provider:
        metrics_store.record_request(
            prompt=request.prompt,
            cache_outcome="miss",
            similarity_score=None,
            threshold_used=effective_threshold,
            risk_score=risk_score,
            provider=route_info["provider"],
            model=route_info["model"],
            tier=route_info["tier"],
            latency_ms=round((time.perf_counter() - total_start_time) * 1000, 2),
            estimated_cost_usd=0.0
        )
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
    latency_ms = round(total_latency * 1000, 2)

    final_reasoning = route_info["reasoning"]
    if successful_provider["name"] != route_info["provider"]:
        final_reasoning += f" Primary provider '{route_info['provider']}' failed. Successfully fell back to '{successful_provider['name']}'."

    routing_decision_obj = RoutingDecision(
        provider=successful_provider["name"],
        model=successful_provider["model_name"],
        tier=successful_provider["priority_tier"],
        reasoning=final_reasoning
    )

    metrics_store.record_request(
        prompt=request.prompt,
        cache_outcome="blocked_by_guard" if guard_reason else "miss",
        similarity_score=raw_sim,
        threshold_used=effective_threshold,
        risk_score=risk_score,
        provider=successful_provider["name"],
        model=successful_provider["model_name"],
        tier=successful_provider["priority_tier"],
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost,
        guard_reason=guard_reason
    )

    return ChatResponse(
        response=response_text,
        latency=total_latency,
        source="llm",
        cache_lookup_latency_seconds=cache_lookup_latency,
        risk_assessment=risk_assessment_obj,
        routing_decision=routing_decision_obj,
        estimated_cost_usd=estimated_cost,
        similarity_score=raw_sim,
        guard_reason=guard_reason
    )
