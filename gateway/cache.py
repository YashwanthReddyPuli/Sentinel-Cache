"""
Qdrant Vector Database Cache Client for SentinelCache.

Provides collection creation, adaptive vector similarity lookup, and cache storage.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

logger = logging.getLogger("sentinelcache.cache")

COLLECTION_NAME = "prompt_cache"
VECTOR_DIMENSION = 384  # all-MiniLM-L6-v2 output dimension

# Named constant for legacy fixed threshold benchmarking
FIXED_THRESHOLD = 0.92


def map_risk_to_threshold(risk_score: float) -> float:
    """
    Linearly maps a prompt risk_score in [0.0, 1.0] to a similarity threshold in [0.88, 0.99].

    Formula: threshold = 0.88 + 0.11 * risk_score
    - risk_score 0.0 -> threshold 0.88
    - risk_score 1.0 -> threshold 0.99

    :param risk_score: Risk score between 0.0 and 1.0
    :return: Mapped similarity threshold float
    """
    clamped_risk = max(0.0, min(1.0, float(risk_score)))
    threshold = 0.88 + (0.11 * clamped_risk)
    return round(threshold, 4)


class CacheClient:
    """Wrapper around QdrantClient for managing prompt_cache collection and queries."""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or os.getenv("QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("QDRANT_PORT", "6333"))
        logger.info(f"Connecting to Qdrant at {self.host}:{self.port}...")
        self.client = QdrantClient(host=self.host, port=self.port)

    def create_collection(self) -> None:
        """
        Creates the 'prompt_cache' collection with 384 dimensions and Cosine distance
        if it does not already exist.
        """
        try:
            if not self.client.collection_exists(COLLECTION_NAME):
                logger.info(f"Collection '{COLLECTION_NAME}' does not exist. Creating...")
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=VECTOR_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection '{COLLECTION_NAME}' created successfully.")
            else:
                logger.info(f"Collection '{COLLECTION_NAME}' already exists.")
        except Exception as exc:
            logger.error(f"Error checking/creating Qdrant collection '{COLLECTION_NAME}': {exc}")
            raise

    def lookup(
        self,
        embedding: list[float],
        risk_score: float = None,
        threshold: float = None
    ) -> dict | None:
        """
        Searches the collection for the single nearest neighbor vector using adaptive thresholding.

        :param embedding: 384-dimensional query vector
        :param risk_score: Optional risk score in [0.0, 1.0] used to map adaptive threshold
        :param threshold: Optional fixed similarity threshold override
        :return: Payload dictionary if similarity >= effective_threshold, else None
        """
        if risk_score is not None:
            effective_threshold = map_risk_to_threshold(risk_score)
        elif threshold is not None:
            effective_threshold = threshold
        else:
            effective_threshold = FIXED_THRESHOLD

        try:
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=embedding,
                limit=1
            )
            points = results.points
            if not points:
                return None

            top_match = points[0]
            similarity_score = top_match.score

            if similarity_score >= effective_threshold:
                payload = top_match.payload or {}
                payload["similarity_score"] = similarity_score
                payload["effective_threshold"] = effective_threshold
                logger.info(f"Cache HIT! Similarity score {similarity_score:.4f} >= threshold {effective_threshold:.4f}")
                return payload
            else:
                logger.info(f"Cache MISS. Similarity score {similarity_score:.4f} < threshold {effective_threshold:.4f}")
                return None

        except Exception as exc:
            logger.warning(f"Qdrant lookup failed: {exc}. Falling back to cache miss.")
            return None

    def store(self, prompt: str, embedding: list[float], response: str) -> None:
        """
        Upserts an embedding vector and payload into the 'prompt_cache' collection.

        :param prompt: Original user prompt string
        :param embedding: 384-dimensional vector
        :param response: LLM response string
        """
        try:
            point_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            payload = {
                "prompt": prompt,
                "response": response,
                "timestamp": timestamp
            }

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )

            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=[point]
            )
            logger.info(f"Stored prompt embedding in cache (ID: {point_id}).")

        except Exception as exc:
            logger.error(f"Failed to store entry in Qdrant cache: {exc}")
