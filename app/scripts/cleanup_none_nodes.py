"""
Cleanup Script — Purge 'TECH_none' Nodes.
=========================================
Removes accidental 'NONE' canonical nodes created during LLM normalizer testing.

Actions:
  1. Deletes nodes with canonical_id = 'TECH_none' from Neo4j.
  2. Deletes points with canonical_id = 'TECH_none' from Qdrant 'onet_skills' collection.
"""

from qdrant_client.http import models as qdrant_models
from app.clients.graph_client import graph_client
from app.clients.vector_client import vector_client
from app.config import settings
from app.utils.logger import logger

ONET_COLLECTION = "onet_skills"
TARGET_CID      = "TECH_none"

def cleanup_neo4j():
    logger.info(f"Cleaning up '{TARGET_CID}' from Neo4j...")
    try:
        with graph_client.driver.session(database=settings.NEO4J_DATABASE) as session:
            # Delete the node and its relationships
            result = session.run(
                "MATCH (t {canonical_id: $cid}) DETACH DELETE t RETURN count(t) AS deleted_count",
                cid=TARGET_CID
            ).single()
            count = result["deleted_count"] if result else 0
            logger.info(f"Neo4j: Deleted {count} nodes matching '{TARGET_CID}'.")
    except Exception as e:
        logger.error(f"Neo4j Cleanup Error: {e}")

import uuid

def cleanup_qdrant():
    logger.info("Cleaning up 'NONE' variants from Qdrant...")
    variants = ["TECH_none", "TECH_NONE", "TECH_None"]
    
    for variant in variants:
        # Calculate the same UUID5 used in skill_normalizer.py
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, variant))
        logger.info(f"Targeting Qdrant Point ID: {point_id} ({variant})")
        
        try:
            vector_client.client.delete(
                collection_name=ONET_COLLECTION,
                points_selector=[point_id]
            )
            logger.info(f"Qdrant: Deletion command sent for {point_id}")
        except Exception as e:
            logger.warning(f"Qdrant point {point_id} not found or error: {e}")

if __name__ == "__main__":
    print("\n--- Starting DB Cleanup ---")
    cleanup_neo4j()
    cleanup_qdrant()
    print("--- Cleanup Complete ---\n")
