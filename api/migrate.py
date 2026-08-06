import os
import json
import uuid
from database import db
from dotenv import load_dotenv
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def create_tables():
    """Create database tables with proper error handling"""
    logger.info("🔄 Creating database tables...")
    
    queries = [
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(36) REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON chat_messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON chat_sessions(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON chat_sessions(updated_at)"
    ]
    
    for i, query in enumerate(queries):
        try:
            db.execute_query(query, fetch="none")
            logger.info(f"✅ Query {i+1} executed successfully")
        except Exception as e:
            logger.error(f"❌ Query {i+1} failed: {e}")
            raise
    
    logger.info("✅ Database tables created successfully")

def migrate_json_data():
    """Migrate existing JSON data with proper validation"""
    json_file = "chat_history.json"
    
    if not os.path.exists(json_file):
        logger.info("ℹ️ No existing JSON data to migrate")
        return
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"🔄 Migrating {len(data)} sessions from JSON to PostgreSQL...")
        
        migrated_sessions = 0
        migrated_messages = 0
        
        for session in data:
            try:
                # Generate UUID if not present
                session_id = session.get("id", str(uuid.uuid4()))
                title = session.get("title", "Untitled")
                created_at = session.get("created_at", datetime.now().isoformat())
                updated_at = session.get("updated_at", datetime.now().isoformat())
                
                # Insert session
                session_query = """
                    INSERT INTO chat_sessions (id, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """
                
                db.execute_query(
                    session_query,
                    (session_id, title, created_at, updated_at),
                    fetch="none"
                )
                
                # Insert messages
                for message in session.get("messages", []):
                    try:
                        msg_query = """
                            INSERT INTO chat_messages (session_id, role, content, created_at, metadata)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        
                        db.execute_query(
                            msg_query,
                            (
                                session_id,
                                message.get("role", "user"),
                                message.get("content", ""),
                                message.get("created_at", datetime.now().isoformat()),
                                json.dumps(message.get("metadata", {}))
                            ),
                            fetch="none"
                        )
                        migrated_messages += 1
                    except Exception as e:
                        logger.warning(f"Failed to migrate message: {e}")
                
                migrated_sessions += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate session: {e}")
                continue
        
        logger.info(f"✅ Successfully migrated {migrated_sessions} sessions and {migrated_messages} messages")
        
        # Backup original JSON file
        backup_file = f"{json_file}.backup"
        os.rename(json_file, backup_file)
        logger.info(f"📦 Original JSON file backed up as {backup_file}")
        
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        raise

def test_database():
    """Test database operations with cleanup"""
    logger.info("🧪 Testing database operations...")
    
    test_session_id = None
    try:
        # Create test session
        session = db.create_session("Test Session - Migration")
        test_session_id = session["id"]
        logger.info(f"✅ Created test session: {test_session_id}")
        
        # Add test message
        message = db.add_message(
            session_id=test_session_id,
            role="user",
            content="Hello, this is a test message!",
            metadata={"test": True, "migration": True}
        )
        logger.info(f"✅ Added test message: {message['id']}")
        
        # Retrieve messages
        messages = db.get_messages(test_session_id)
        logger.info(f"✅ Retrieved {len(messages)} message(s)")
        
        # Test listing sessions
        sessions = db.list_sessions()
        logger.info(f"✅ Retrieved {len(sessions)} session(s) from list")
        
        logger.info("✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        # Clean up test data
        if test_session_id:
            try:
                db.delete_session(test_session_id)
                logger.info("🧹 Cleaned up test data")
            except Exception as e:
                logger.warning(f"Failed to clean up test data: {e}")

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting database migration...")
        create_tables()
        migrate_json_data()
        test_database()
        logger.info("✅ Migration completed successfully!")
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        exit(1)
