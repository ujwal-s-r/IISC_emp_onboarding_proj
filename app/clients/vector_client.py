from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import ClientConnectionError

class VectorClient:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )

    def test_connection(self):
        logger.info(f"Testing connection to Qdrant at {settings.QDRANT_URL}")
        try:
            collections = self.client.get_collections()
            logger.info(f"Qdrant connection successful. Found {len(collections.collections)} collections.")
            return True
        except Exception as e:
            logger.error(f"Qdrant connection error: {str(e)}")
            return False

vector_client = VectorClient()

