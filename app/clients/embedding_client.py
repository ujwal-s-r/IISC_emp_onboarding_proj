from sentence_transformers import SentenceTransformer
from typing import List
from app.utils.logger import logger


class EmbeddingClient:
    """
    Local embedding client using intfloat/multilingual-e5-small.
    Produces 384-dimensional dense vectors.
    The model expects prompts prefixed with 'query: ' for queries
    and 'passage: ' for documents being indexed.
    """
    MODEL_NAME = "intfloat/multilingual-e5-small"
    VECTOR_SIZE = 384

    def __init__(self):
        logger.info(f"Loading embedding model: {self.MODEL_NAME}")
        self.model = SentenceTransformer(self.MODEL_NAME)
        logger.info("Embedding model loaded successfully.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents (for indexing into Qdrant)."""
        prefixed = [f"passage: {t}" for t in texts]
        embeddings = self.model.encode(prefixed, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string (for searching Qdrant)."""
        embedding = self.model.encode(
            [f"query: {text}"], normalize_embeddings=True
        )
        return embedding[0].tolist()


# Singleton instance — imported by the ingestion script
embedding_client = EmbeddingClient()
