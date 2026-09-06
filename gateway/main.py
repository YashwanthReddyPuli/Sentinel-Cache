import os
import time
import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="SentinelCache Baseline Gateway",
    description="Cloud-native AI API gateway with complexity-aware semantic caching & dynamic routing baseline",
    version="0.1.0"
)

# Groq API Configuration
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text to pass to the LLM", min_length=1)


class ChatResponse(BaseModel):
    response: str = Field(..., description="LLM generated output text")
    latency: float = Field(..., description="Full round-trip latency in seconds")
    source: str = Field(default="llm", description="Origin of response (llm or cache)")


@app.get("/")
async def root():
    """Health check & baseline info endpoint."""
    return {
        "status": "ok",
        "service": "SentinelCache Baseline Gateway",
        "version": "0.1.0"
    }


@app.post(
    "/v1/chat/completions",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send prompt to LLM provider (Groq)"
)
async def chat_completions(request: ChatRequest):
    """
    Passthrough endpoint for LLM chat completion.
    
    Measures round-trip latency to Groq API using model llama-3.1-8b-instant.
    """
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

    start_time = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(GROQ_API_URL, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        end_time = time.perf_counter()
        latency = round(end_time - start_time, 4)

        # Extract text content from OpenAI-compatible choice format
        response_text = data["choices"][0]["message"]["content"]

        return ChatResponse(
            response=response_text,
            latency=latency,
            source="llm"
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
