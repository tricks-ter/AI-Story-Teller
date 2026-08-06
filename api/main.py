from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
from datetime import datetime
import logging
from database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager (modern FastAPI approach)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting AI Story Teller API...")
    try:
        if db.test_connection():
            logger.info("✅ Database connection successful")
        else:
            logger.warning("⚠️ Database connection failed - running in degraded mode")
    except Exception as e:
        logger.error(f"❌ Startup database error: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    db.close_all()

app = FastAPI(
    title="AI Story Teller API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class SessionCreate(BaseModel):
    title: str = "New Chat"

class MessageCreate(BaseModel):
    session_id: str
    role: str
    content: str
    metadata: Optional[dict] = None

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime
    metadata: Optional[dict] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected" if db.test_connection() else "disconnected",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/sessions", response_model=SessionResponse)
async def create_session(session: SessionCreate):
    """Create a new chat session"""
    try:
        result = db.create_session(session.title)
        
        return SessionResponse(
            id=str(result["id"]),  # Ensure string conversion
            title=result["title"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            message_count=0
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all chat sessions"""
    try:
        results = db.list_sessions()
        
        return [
            SessionResponse(
                id=str(row["id"]),
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"]
            )
            for row in results
        ]
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(session_id: str):
    """Get all messages from a session"""
    try:
        results = db.get_messages(session_id)
        
        return [
            MessageResponse(
                id=row["id"],
                session_id=str(row["session_id"]),
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
                metadata=row["metadata"] if row["metadata"] else None
            )
            for row in results
        ]
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and all its messages"""
    try:
        db.delete_session(session_id)
        return {"message": "Session deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/chat/stream")
async def chat_stream(message: MessageCreate):
    """Stream chat response with actual Z.AI integration"""
    try:
        # Save user message to database
        user_message = db.add_message(
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            metadata=message.metadata
        )
        
        # Integrate with Z.AI SDK here
        # Example implementation:
        from zai import ZAIClient
        import os
        
        zai_client = ZAIClient(api_key=os.getenv("ZAI_API_KEY"))
        
        # Get conversation history
        messages = db.get_messages(message.session_id)
        conversation = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
        
        # Call Z.AI API
        response = zai_client.chat.create(
            model="glm-4",  # or appropriate model
            messages=conversation,
            stream=False
        )
        
        # Save assistant response
        assistant_message = db.add_message(
            session_id=message.session_id,
            role="assistant",
            content=response.choices[0].message.content,
            metadata={"model": "glm-4", "tokens": response.usage.total_tokens}
        )
        
        return {
            "message_id": assistant_message["id"],
            "session_id": message.session_id,
            "role": "assistant",
            "content": response.choices[0].message.content,
            "created_at": assistant_message["created_at"].isoformat()
        }
        
    except ImportError:
        logger.warning("Z.AI SDK not installed, using placeholder")
        return {
            "message_id": user_message["id"],
            "session_id": message.session_id,
            "role": "assistant",
            "content": "Z.AI SDK not configured. This is a placeholder response.",
            "created_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in chat stream: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")
