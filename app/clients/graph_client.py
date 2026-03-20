from neo4j import GraphDatabase
from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import ClientConnectionError

class GraphClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def test_connection(self):
        logger.info(f"Testing connection to Neo4j at {settings.NEO4J_URI}")
        try:
            with self.driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run("RETURN 1 AS result")
                record = result.single()
                if record and record["result"] == 1:
                    logger.info("Neo4j connection successful.")
                    return True
            return False
        except Exception as e:
            logger.error(f"Neo4j connection error: {str(e)}")
            return False

graph_client = GraphClient()

