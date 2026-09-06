"""
Embedding Model Wrapper for SentinelCache.

Loads the sentence-transformers model 'all-MiniLM-L6-v2' once at module import time
so the model instance is reused across requests without reloading overhead.

Note: ONNX export/runtime execution is a planned future optimization for higher throughput
and lower CPU embedding latency, but is not required for correctness in Phase 1.
"""

import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("sentinelcache.embedding")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Load the model once at module import time
logger.info(f"Loading embedding model '{MODEL_NAME}'...")
_default_model_instance = SentenceTransformer(MODEL_NAME)
logger.info(f"Embedding model '{MODEL_NAME}' loaded successfully.")


class EmbeddingModel:
    """Wrapper class providing text-to-vector embedding interface."""

    def __init__(self, model: SentenceTransformer = None):
        # Reuse module-level preloaded model instance by default
        self.model = model or _default_model_instance

    def embed(self, text: str) -> list[float]:
        """
        Embeds a text string into a 384-dimensional floating point vector.

        :param text: Input prompt text string
        :return: 384-dimensional float vector list
        """
        if not text or not text.strip():
            raise ValueError("Text string for embedding cannot be empty.")

        embedding_vector = self.model.encode(text, convert_to_numpy=True)
        return embedding_vector.tolist()
