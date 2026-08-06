import os
import psycopg2
from psycopg2 import sql, extras
from psycopg2.pool import SimpleConnectionPool
from typing import Optional, Dict, List, Any
import json
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool: Optional[SimpleConnectionPool] = None
        self.database_url = os.getenv("DATABASE_URL")
        
        # Initialize connection pool
        if self.database_url:
            self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool with proper SSL handling"""
        try:
            # Parse and fix connection string for SSL
            db_url = self.database_url
            
            # Ensure SSL is required for Neon
            if "sslmode" not in db_url:
                separator = "&" if "?" in db_url else "?"
                db_url += f"{separator}sslmode=require"
            
            # Create connection pool
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=5,  # Reduced for serverless compatibility
                dsn=db_url
            )
            logger.info("✅ Database connection pool initialized")
            
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            raise
    
    def get_connection(self):
        """Get connection from pool with fallback"""
        if not self.pool:
            self._initialize_pool()
        
        try:
            return self.pool.getconn()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            # Fallback: create direct connection
            return psycopg2.connect(self.database_url)
    
    def return_connection(self, conn):
        """Return connection to pool safely"""
        if self.pool and conn:
            try:
                self.pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Error returning connection: {e}")
                conn.close()
    
    def execute_query(self, query: str, params: tuple = None, fetch: str = "all") -> Any:
        """
        Execute SQL query with parameters and proper error handling
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # Execute query
            cursor.execute(query, params or ())
            
            # Fetch results if needed
            if fetch == "all":
                results = cursor.fetchall()
            elif fetch == "one":
                results = cursor.fetchone()
            else:
                results = None
                conn.commit()
            
            return results
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database query error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.return_connection(conn)
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            result = self.execute_query("SELECT 1 as test", fetch="one")
            return result is not None
        except Exception:
            return False
    
    # ... (keep other methods same as before)

# Global database instance
db = Database()
