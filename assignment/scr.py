"""
Chat Management API

This FastAPI application provides a comprehensive system for managing chat conversations,
including storage, retrieval, summarization, and deletion of chats.

Key Features:
- Store chat messages in MongoDB
- Retrieve individual and user chat histories
- Summarize conversations using Mistral AI
- Secure chat management with optional user verification
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
import os
import httpx
import math
from dotenv import load_dotenv
load_dotenv()
# Initialize FastAPI application
app = FastAPI(
    title="Chat Management API",
    description="Manage and analyze chat conversations",
    version="1.0.0"
)

# Database Configuration
# Note: In production, use environment variables for sensitive information
MONGO_URL = os.getenv("MONGO_URL")
client = AsyncIOMotorClient(MONGO_URL)
db = client["notes"]
collection = db["chats"]

# API Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

# Data Models
class Message(BaseModel):
    """
    Represents an individual message in a chat.
    
    Attributes:
    - sender: Who sent the message
    - text: Content of the message
    - timestamp: When the message was sent
    """
    sender: str
    text: str
    timestamp: datetime

class Chat(BaseModel):
    """
    Represents a complete chat conversation.
    
    Attributes:
    - user_id: Identifier for the user
    - messages: List of messages in the conversation
    """
    user_id: str
    messages: List[Message]

@app.post("/chats", summary="Store a New Chat")
async def store_chat(chat: Chat):
    """
    Save a new chat conversation to the database.
    
    Args:
    - chat: Chat object containing user ID and messages
    
    Returns:
    - Confirmation message with generated chat ID
    """
    # Convert chat to dictionary and add creation timestamp
    chat_data = chat.dict()
    chat_data["created_at"] = datetime.utcnow()
    
    # Insert chat and return ID
    result = await collection.insert_one(chat_data)
    return {
        "message": "Chat stored successfully!", 
        "chat_id": str(result.inserted_id)
    }

@app.get("/chats/{chat_id}", summary="Retrieve Specific Chat")
async def get_chat(chat_id: str):
    """
    Retrieve a specific chat by its ID.
    
    Args:
    - chat_id: Unique identifier for the chat
    
    Returns:
    - Complete chat details
    
    Raises:
    - HTTPException for invalid or not found chats
    """
    try:
        # Validate chat ID format
        if not ObjectId.is_valid(chat_id):
            raise HTTPException(status_code=400, detail="Invalid chat ID")
        
        # Fetch chat from database
        chat = await collection.find_one({"_id": ObjectId(chat_id)})

        if chat:
            # Convert MongoDB ObjectId to string
            chat["_id"] = str(chat["_id"])
            return chat
        
        raise HTTPException(status_code=404, detail="Chat not found")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/chats/summarize", summary="Generate Chat Summary")
async def summarize_chat(conversation_id: str = Query(..., description="ID of chat to summarize")):
    """
    Generate a concise summary of a chat conversation using Mistral AI.
    
    Args:
    - conversation_id: Unique identifier for the chat
    
    Returns:
    - Generated summary with metadata
    
    Raises:
    - HTTPException for various potential errors
    """
    try:
        # Validate and retrieve chat
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(status_code=400, detail="Invalid conversation ID")
        
        chat = await collection.find_one({"_id": ObjectId(conversation_id)})
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Prepare conversation text
        chat_text = "\n".join([msg["text"] for msg in chat["messages"]])
        
        # Prepare API request to Mistral
        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistral-large-latest",
            "messages": [
                {"role": "system", "content": "Summarize conversations concisely."},
                {"role": "user", "content": f"Summarize this conversation:\n\n{chat_text}"}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }

        # Make API request with error handling
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.post(MISTRAL_API_URL, json=payload, headers=headers)
            
            # Validate and process response
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Summarization failed: {response.status_code}"
                )

            summary = response.json()["choices"][0]["message"]["content"]
            
            return {
                "conversation_id": conversation_id, 
                "summary": summary,
                "summary_length": len(summary)
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization error: {str(e)}")

@app.get("/users/{user_id}/chats", summary="Retrieve User's Chat History")
async def get_user_chats(
    user_id: str, 
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Number of chats per page")
):
    """
    Retrieve paginated chat history for a specific user.
    
    Args:
    - user_id: Identifier for the user
    - page: Page number for pagination
    - limit: Number of chats per page
    
    Returns:
    - Paginated chat history with metadata
    """
    try:
        # Count total user chats
        total_chats = await collection.count_documents({"user_id": user_id})
        total_pages = math.ceil(total_chats / limit)
        
        # Validate page number
        if page > total_pages and total_pages > 0:
            raise HTTPException(
                status_code=404, 
                detail=f"Page {page} does not exist. Total pages: {total_pages}"
            )
        
        # Retrieve paginated chats
        cursor = collection.find({"user_id": user_id}) \
            .skip((page - 1) * limit) \
            .limit(limit) \
            .sort("created_at", -1)
        
        chats = await cursor.to_list(length=limit)
        
        # Convert ObjectIds to strings
        for chat in chats:
            chat["_id"] = str(chat["_id"])
        
        return {
            "user_id": user_id,
            "chats": chats,
            "page": page,
            "limit": limit,
            "total_chats": total_chats,
            "total_pages": total_pages
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chats: {str(e)}")

@app.delete("/chats/{conversation_id}", summary="Delete a Chat")
async def delete_chat(
    conversation_id: str, 
    user_id: str = Query(None, description="Optional user ID for verification")
):
    """
    Delete a specific chat, with optional user verification.
    
    Args:
    - conversation_id: ID of chat to delete
    - user_id: Optional user ID for additional security
    
    Returns:
    - Deletion confirmation
    """
    try:
        # Validate conversation ID
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(status_code=400, detail="Invalid chat ID")
        
        # Prepare deletion query
        delete_query = {"_id": ObjectId(conversation_id)}
        if user_id:
            delete_query["user_id"] = user_id
        
        # Perform deletion
        result = await collection.delete_one(delete_query)
        
        # Check deletion result
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail="Chat not found" + 
                (" or not associated with the specified user" if user_id else "")
            )
        
        return {
            "message": "Chat deleted successfully!",
            "deleted_count": result.deleted_count
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting chat: {str(e)}")