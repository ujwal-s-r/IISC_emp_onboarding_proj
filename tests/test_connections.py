import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.clients.llm_client import llm_client
from app.clients.vector_client import vector_client
from app.clients.graph_client import graph_client
from app.utils.logger import logger

async def test_all_connections():
    logger.info("Starting connection tests for all clients...")
    
    # Test Neo4j
    neo4j_ok = graph_client.test_connection()
    
    # Test Qdrant
    qdrant_ok = vector_client.test_connection()
    
    # Test OpenRouter (Async)
    llm_ok = await llm_client.test_connection()
    
    logger.info("--- Connection Test Summary ---")
    logger.info(f"Neo4j: {'SUCCESS' if neo4j_ok else 'FAILED'}")
    logger.info(f"Qdrant: {'SUCCESS' if qdrant_ok else 'FAILED'}")
    logger.info(f"OpenRouter: {'SUCCESS' if llm_ok else 'FAILED'}")
    
    if neo4j_ok and qdrant_ok and llm_ok:
        logger.info("All connections validated successfully.")
    else:
        logger.error("Some connections failed. Check logs above.")

if __name__ == "__main__":
    asyncio.run(test_all_connections())
