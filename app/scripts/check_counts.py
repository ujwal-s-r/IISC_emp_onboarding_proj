from app.clients.graph_client import GraphClient
from app.config import settings

def main():
    gc = GraphClient()
    print("Checking Neo4j counts...")
    try:
        with gc.driver.session(database=settings.NEO4J_DATABASE) as session:
            occ_count = session.run("MATCH (n:Occupation) RETURN count(n) AS c").single()["c"]
            tech_count = session.run("MATCH (n:Technology) RETURN count(n) AS c").single()["c"]
            skill_count = session.run("MATCH (n:Skill) RETURN count(n) AS c").single()["c"]
            rel_uses = session.run("MATCH ()-[r:USES_TECH]->() RETURN count(r) AS c").single()["c"]
            rel_req = session.run("MATCH ()-[r:REQUIRES_SKILL]->() RETURN count(r) AS c").single()["c"]
            
            print("\n--- Current Neo4j Database Counts ---")
            print(f"Occupations Nodes:     {occ_count}")
            print(f"Technology Nodes:      {tech_count}")
            print(f"Skill Nodes:           {skill_count}")
            print(f"USES_TECH Rels:        {rel_uses}")
            print(f"REQUIRES_SKILL Rels:   {rel_req}")
            print("-------------------------------------")
    except Exception as e:
        print(f"Error querying Neo4j: {e}")
    finally:
        gc.close()

if __name__ == "__main__":
    main()
