"""
Base Memory Class
Provides common Neo4j connection functionality for all memory systems
"""

from neo4j import GraphDatabase

class BaseNeo4jMemory:
    """Base class for Neo4j-based memory systems"""
    
    def __init__(self, neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="12345678"):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close Neo4j connection"""
        self.driver.close() 