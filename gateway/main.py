import os
import time
import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from embedding.embedder import EmbeddingModel
from gateway.cache import CacheClient

# Load environment variables
load_dotenv()

# Logger setup
logger = logging.getLogger("sentinelcache.gateway")
logging.basicConfig(level=logging.INFO)

# Groq API Configuration
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Semantic Cache Configuration
# Fixed similarity threshold for Phase 1 (to be replaced with dynamic scoring in Phase 2)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.92"))

# Global model and cache client instances
embedder: EmbeddingModel = None
cache_client: CacheClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to initialize embedding model and cache client on startup."""
    global embedder, cache_client
    logger.info("Initializing SentinelCache gateway resources...")

    # Load embedding model and initialize cache client
    embedder = EmbeddingModel()
    cache_client = CacheClient()

    # Create Qdrant collection if missing
    try:
        cache_client.create_collection()
    except Exception as exc:
        logger.warning(f"Qdrant collection initialization warning: {exc}. Gateway will run in passthrough mode.")

    yield

    logger.info("Shutting down SentinelCache gateway resources...")


app = FastAPI(
    title="SentinelCache API Gateway",
    description="Cloud-native AI API gateway with complexity-aware semantic caching & dynamic routing",
    version="0.2.0",
    lifespan=lifespan
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text to pass to the LLM", min_length=1)


class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM generated or cached response text")
    latency: float = Field(..., description="Full round-trip request latency in seconds")
    source: str = Field(..., description="Origin of response ('llm' or 'cache')")
    cache_lookup_latency_seconds: float = Field(..., description="Overhead latency for embedding & Qdrant vector lookup in seconds")


@app.get("/")
async def root():
    """Health check & status endpoint."""
    return {
        "status": "ok",
        "service": "SentinelCache Gateway",
        "version": "0.2.0",
        "similarity_threshold": SIMILARITY_THRESHOLD
    }


@app.post(
    "/v1/chat/completions",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send prompt with semantic cache lookup and Groq LLM fallback"
)
async def chat_completions(request: ChatRequest):
    """
    Handles prompt completion requests:
    1. Embeds prompt and searches Qdrant prompt_cache vector store.
    2. If Cosine similarity >= 0.92 (cache hit), returns cached response immediately.
    3. If cache miss, sends prompt to Groq LLM API, stores prompt/vector/response in Qdrant, and returns response.
    """
    total_start_time = time.perf_counter()

    # ----------------------------------------------------
    # Step 1: Semantic Vector Cache Lookup
    # ----------------------------------------------------
    cache_start_time = time.perf_counter()
    cached_hit = None
    prompt_embedding = None

    if embedder and cache_client:
        try:
            prompt_embedding = embedder.embed(request.prompt)
            cached_hit = cache_client.lookup(prompt_embedding, threshold=SIMILARITY_THRESHOLD)
        except Exception as exc:
            logger.warning(f"Cache lookup failed: {exc}. Proceeding to LLM provider.")

    cache_lookup_latency = round(time.perf_counter() - cache_start_time, 4)

    # ----------------------------------------------------
    # Step 2: Handle Cache HIT
    # ----------------------------------------------------
    if cached_hit is not None:
        total_latency = round(time.perf_counter() - total_start_time, 4)
        return ChatResponse(
            response=cached_hit["response"],
            latency=total_latency,
            source="cache",
            cache_lookup_latency_seconds=cache_lookup_latency
        )

    # ----------------------------------------------------
    # Step 3: Handle Cache MISS -> Query Groq LLM Provider
    # ----------------------------------------------------
    load_dotenv(override=True)
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key.startswith("your_"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GROQ_API_KEY environment variable is not configured. Please set a valid key in .env."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": request.prompt}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(GROQ_API_URL, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        response_text = data["choices"][0]["message"]["content"]

        # Store response in Qdrant prompt_cache for future cache hits
        if cache_client and prompt_embedding is not None:
            try:
                cache_client.store(request.prompt, prompt_embedding, response_text)
            except Exception as exc:
                logger.warning(f"Failed to store entry in cache: {exc}")

        total_latency = round(time.perf_counter() - total_start_time, 4)

        return ChatResponse(
            response=response_text,
            latency=total_latency,
            source="llm",
            cache_lookup_latency_seconds=cache_lookup_latency
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to Groq API timed out after 30 seconds."
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Groq API returned HTTP error: {exc.response.text}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while processing request: {str(exc)}"
        )
