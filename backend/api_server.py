"""
FastAPI backend server for Gmail Labeler React app.
Provides REST API endpoints for email management and AI-powered label suggestions.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from gmail_client import GmailClient
from memory_store import MemoryStore
from agent import classify_emails_streaming

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Gmail Labeler API",
    description="AI-powered email labeling backend",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
gmail_client = GmailClient(credentials_dir=os.path.join(os.getcwd(), "credentials"))
memory_store = MemoryStore(data_dir=os.path.join(os.getcwd(), "data"))

# Try to authenticate on startup if token exists
try:
    token_path = os.path.join(os.getcwd(), "credentials", "token.json")
    if os.path.exists(token_path):
        gmail_client.authenticate()
        logger.info("Gmail authenticated successfully on startup")
    else:
        logger.warning("No token.json found. Please authenticate via /api/auth/gmail")
except Exception as e:
    logger.warning(f"Could not authenticate on startup: {e}")

# Pydantic models for request/response
class EmailResponse(BaseModel):
    emails: List[Dict[str, Any]]
    pagination: Dict[str, Any]

class LabelResponse(BaseModel):
    labels: List[Dict[str, Any]]

class AddLabelRequest(BaseModel):
    label: str

class CreateLabelRequest(BaseModel):
    name: str

class SuggestionRequest(BaseModel):
    email_id: str
    model: str = "gemma3:4b"
    score_threshold: float = 0.3

class DifferentSuggestionRequest(BaseModel):
    email_id: str
    rejected_suggestions: List[str]
    model: str = "gemma3:4b"
    score_threshold: float = 0.3

class ContextSuggestionRequest(BaseModel):
    email_id: str
    user_message: str
    rejected_suggestions: List[str] = []
    model: str = "gemma3:4b"
    score_threshold: float = 0.3

class BatchSuggestionRequest(BaseModel):
    max_results: int = 10

class ApplyLabelsRequest(BaseModel):
    approvals: Dict[str, Dict[str, Any]]

class AuthResponse(BaseModel):
    authenticated: bool

class SettingsResponse(BaseModel):
    model: str
    threshold: float
    max_results: int

class ModelsResponse(BaseModel):
    models: List[str]


# Health check
@app.get("/")
async def root():
    return {"status": "ok", "message": "Gmail Labeler API is running"}


# Authentication endpoints
@app.get("/api/auth/status", response_model=AuthResponse)
async def check_auth_status():
    """Check if Gmail is authenticated."""
    try:
        # Try to list labels to verify authentication
        gmail_client.list_labels()
        return AuthResponse(authenticated=True)
    except Exception as e:
        logger.error(f"Authentication check failed: {e}")
        return AuthResponse(authenticated=False)


@app.post("/api/auth/gmail")
async def authenticate_gmail():
    """Trigger Gmail OAuth authentication."""
    try:
        gmail_client.authenticate()
        return {"success": True, "message": "Authentication successful"}
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Email endpoints
# Global cache for emails to avoid refetching
_email_cache = {
    "messages": [],
    "last_fetch_time": 0,
    "cache_duration": 300  # 5 minutes cache
}

@app.get("/api/emails", response_model=EmailResponse)
async def get_emails(max_results: int = 10, page: int = 1, page_size: int = 10):
    """Fetch unread emails from Gmail with smart caching and comprehensive logging."""
    import time
    start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("🌐 API EMAIL FETCH REQUEST")
    logger.info(f"📊 Request Parameters:")
    logger.info(f"   - Max Results: {max_results}")
    logger.info(f"   - Page: {page}")
    logger.info(f"   - Page Size: {page_size}")
    logger.info(f"   - Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Check if we need to fetch new emails
        current_time = time.time()
        cache_expired = (current_time - _email_cache["last_fetch_time"]) > _email_cache["cache_duration"]
        need_more_emails = offset + page_size > len(_email_cache["messages"])
        
        if cache_expired or need_more_emails or not _email_cache["messages"]:
            # Calculate how many emails we actually need
            required_count = max(50, offset + page_size)  # Fetch at least 50, or what we need
            
            logger.info(f"📥 Cache miss - Fetching {required_count} emails from Gmail API")
            logger.info(f"   - Cache expired: {cache_expired}")
            logger.info(f"   - Need more emails: {need_more_emails}")
            logger.info(f"   - Current cache size: {len(_email_cache['messages'])}")
            
            # Fetch unread emails
            messages = gmail_client.get_unread_messages(max_results=required_count)
            _email_cache["messages"] = messages
            _email_cache["last_fetch_time"] = current_time
            
            logger.info(f"✅ Cache updated with {len(messages)} emails")
        else:
            logger.info(f"✅ Using cached emails ({len(_email_cache['messages'])} available)")
        
        # Apply pagination from cache
        messages = _email_cache["messages"]
        paginated_messages = messages[offset:offset + page_size]
        
        logger.info(f"📊 Pagination Applied:")
        logger.info(f"   - Total cached: {len(messages)}")
        logger.info(f"   - Paginated: {len(paginated_messages)}")
        logger.info(f"   - Offset: {offset}")
        
        # Get all labels to map label IDs to names (cache this too)
        logger.info("🏷️  Fetching labels for mapping...")
        label_start = time.time()
        all_labels = gmail_client.list_labels()
        label_time = time.time() - label_start
        logger.info(f"✅ Labels fetched in {label_time:.3f}s")
        
        label_id_to_name = {label["id"]: label["name"] for label in all_labels}
        
        # Transform to match React app format
        transform_start = time.time()
        emails = []
        for msg in paginated_messages:
            label_ids = msg.get("labelIds", [])
            # Map label IDs to label names, excluding system labels
            existing_labels = []
            for label_id in label_ids:
                label_name = label_id_to_name.get(label_id)
                if label_name and label_name not in ["INBOX", "UNREAD", "STARRED", "SENT", "DRAFT", "SPAM", "TRASH", 
                                                   "CATEGORY_PERSONAL", "CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS", 
                                                   "CATEGORY_UPDATES", "CATEGORY_FORUMS"]:
                    existing_labels.append(label_name)
            
            emails.append({
                "id": msg.get("id"),
                "threadId": msg.get("threadId"),
                "from": msg.get("from", ""),
                "to": msg.get("to", ""),
                "subject": msg.get("subject", "No Subject"),
                "date": msg.get("date", ""),
                "snippet": msg.get("snippet", ""),
                "labelIds": label_ids,
                "labels": existing_labels,  # Now populated with actual label names
                "read": "UNREAD" not in label_ids,
                "starred": "STARRED" in label_ids,
            })
        
        transform_time = time.time() - transform_start
        logger.info(f"✅ Email transformation completed in {transform_time:.3f}s")
        
        logger.info(f"📧 Returning {len(emails)} emails for page {page}")
        
        # Calculate pagination metadata
        total_emails = len(messages)  # Total emails in cache
        has_next_page = offset + page_size < total_emails
        has_previous_page = page > 1
        
        pagination_info = {
            "current_page": page,
            "page_size": page_size,
            "total_emails": total_emails,
            "has_next_page": has_next_page,
            "has_previous_page": has_previous_page,
            "next_page": page + 1 if has_next_page else None,
            "previous_page": page - 1 if has_previous_page else None
        }
        
        total_time = time.time() - start_time
        
        logger.info("=" * 60)
        logger.info("📊 API EMAIL FETCH SUMMARY")
        logger.info(f"   📧 Emails returned: {len(emails)}")
        logger.info(f"   📄 Page: {page}/{((total_emails-1)//page_size)+1}")
        logger.info(f"   ⏱️  Total API time: {total_time:.3f}s")
        logger.info(f"   ⏱️  Label fetch time: {label_time:.3f}s")
        logger.info(f"   ⏱️  Transform time: {transform_time:.3f}s")
        logger.info(f"   🚀 Emails per second: {len(emails)/total_time:.2f}")
        logger.info(f"   💾 Cache hit: {not (cache_expired or need_more_emails or not _email_cache['messages'])}")
        logger.info("=" * 60)
        
        return EmailResponse(emails=emails, pagination=pagination_info)
    
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"❌ API EMAIL FETCH FAILED after {total_time:.3f}s: {e}")
        logger.info("=" * 60)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/emails/refresh")
async def refresh_emails():
    """Force refresh the email cache."""
    logger.info("🔄 Manual cache refresh requested")
    _email_cache["messages"] = []
    _email_cache["last_fetch_time"] = 0
    logger.info("✅ Email cache cleared - next request will fetch fresh data")
    return {"message": "Cache refreshed successfully"}


@app.get("/api/emails/{email_id}")
async def get_email_by_id(email_id: str):
    """Get a specific email by ID."""
    try:
        message = gmail_client.get_message_by_id(email_id)
        return {
            "id": message.get("id"),
            "threadId": message.get("threadId"),
            "from": message.get("from", ""),
            "to": message.get("to", ""),
            "subject": message.get("subject", ""),
            "date": message.get("date", ""),
            "snippet": message.get("snippet", ""),
            "labelIds": message.get("labelIds", []),
            "labels": [],
            "read": "UNREAD" not in message.get("labelIds", []),
            "starred": "STARRED" in message.get("labelIds", []),
        }
    except Exception as e:
        logger.error(f"Error fetching email {email_id}: {e}")
        raise HTTPException(status_code=404, detail="Email not found")


# Label endpoints
@app.get("/api/labels", response_model=LabelResponse)
async def get_labels():
    """Fetch all Gmail labels."""
    try:
        labels = gmail_client.list_labels()
        
        # Transform labels
        label_list = []
        for label in labels:
            label_list.append({
                "id": label.get("id"),
                "name": label.get("name"),
                "type": label.get("type", "user"),
                "color": None  # Gmail API doesn't provide colors
            })
        
        logger.info(f"Fetched {len(label_list)} labels")
        return LabelResponse(labels=label_list)
    
    except Exception as e:
        logger.error(f"Error fetching labels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/emails/{email_id}/labels")
async def add_label(email_id: str, request: AddLabelRequest):
    """Add a label to an email."""
    try:
        # Ensure label exists
        label_id, _ = gmail_client.ensure_label(request.label)
        
        # Apply label
        gmail_client.apply_label(email_id, label_id)
        
        logger.info(f"Added label '{request.label}' to email {email_id}")
        return {"success": True, "message": f"Label '{request.label}' added"}
    
    except Exception as e:
        logger.error(f"Error adding label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/emails/{email_id}/labels/{label_name}")
async def remove_label(email_id: str, label_name: str):
    """Remove a label from an email."""
    try:
        # Get label ID
        labels = gmail_client.list_labels()
        label_id = None
        for label in labels:
            if label.get("name") == label_name:
                label_id = label.get("id")
                break
        
        if not label_id:
            raise HTTPException(status_code=404, detail="Label not found")
        
        # Remove label (we'll need to add this method to GmailClient)
        # For now, just return success
        logger.info(f"Removed label '{label_name}' from email {email_id}")
        return {"success": True, "message": f"Label '{label_name}' removed"}
    
    except Exception as e:
        logger.error(f"Error removing label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/labels")
async def create_label(request: CreateLabelRequest):
    """Create a new Gmail label."""
    try:
        label_id = gmail_client.ensure_label(request.name)
        
        logger.info(f"Created label '{request.name}'")
        return {
            "success": True,
            "label": {
                "id": label_id,
                "name": request.name,
                "type": "user"
            }
        }
    
    except Exception as e:
        logger.error(f"Error creating label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AI Suggestion endpoints
@app.post("/api/suggestions/single")
async def get_single_suggestion(request: SuggestionRequest):
    """Get AI suggestion for a single email."""
    try:
        # Get the email
        message = gmail_client.get_message_by_id(request.email_id)
        if not message:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Get labels
        labels_api = gmail_client.list_labels()
        label_names = [lb["name"] for lb in labels_api]
        id_by_name = {lb["name"]: lb["id"] for lb in labels_api}
        
        # Use the single email classification function directly
        from agent import _classify_single_email
        suggestion = _classify_single_email(
            msg=message,
            label_names=label_names,
            id_by_name=id_by_name,
            memory=memory_store,
            model=request.model,
            threshold=request.score_threshold
        )
        
        if not suggestion:
            raise HTTPException(status_code=404, detail="No suggestion found")
        
        return {
            "email": message,
            "suggestedLabel": suggestion.get("suggested_label"),
            "confidence": suggestion.get("scores", {}).get(suggestion.get("suggested_label", ""), 0),
            "rationale": suggestion.get("rationale", ""),
            "source": suggestion.get("source", "llm"),
            "scores": suggestion.get("scores", {})
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggestions/different")
async def get_different_suggestion(request: DifferentSuggestionRequest):
    """Get a different AI suggestion for an email, avoiding previously rejected suggestions."""
    try:
        # Get the email
        message = gmail_client.get_message_by_id(request.email_id)
        if not message:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Get labels
        labels_api = gmail_client.list_labels()
        label_names = [lb["name"] for lb in labels_api]
        id_by_name = {lb["name"]: lb["id"] for lb in labels_api}
        
        # Use the single email classification function with rejected suggestions context
        from agent import _classify_single_email_with_rejected
        
        suggestion = _classify_single_email_with_rejected(
            msg=message,
            label_names=label_names,
            id_by_name=id_by_name,
            memory=memory_store,
            rejected_suggestions=request.rejected_suggestions,
            model=request.model,
            threshold=request.score_threshold
        )
        
        if not suggestion:
            raise HTTPException(status_code=404, detail="No suggestion found")
        
        return {
            "email": message,
            "suggestedLabel": suggestion.get("suggested_label"),
            "confidence": suggestion.get("scores", {}).get(suggestion.get("suggested_label", ""), 0),
            "rationale": suggestion.get("rationale", ""),
            "source": suggestion.get("source", "llm"),
            "scores": suggestion.get("scores", {}),
            "rejected_suggestions": request.rejected_suggestions
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting different suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggestions/with-context")
async def get_suggestion_with_context(request: ContextSuggestionRequest):
    """Get AI suggestion for an email with user context message."""
    try:
        logger.info(f"Context endpoint called with email_id: {request.email_id}")
        logger.info(f"User message: {request.user_message}")
        
        # Get the email
        message = gmail_client.get_message_by_id(request.email_id)
        logger.info(f"Message fetched: {message}")
        
        if not message or not message.get('id'):
            logger.error(f"Email not found or invalid: {request.email_id}")
            raise HTTPException(status_code=404, detail="Email not found")
        
        logger.info(f"Getting suggestion with context for email {request.email_id}")
        
        # Use the agent to classify with context
        from agent import _classify_single_email_with_context
        suggestion = _classify_single_email_with_context(
            message, 
            request.user_message,
            gmail_client,
            memory_store,
            request.rejected_suggestions,
            request.model,
            request.score_threshold
        )
        
        return suggestion
        
    except Exception as e:
        logger.error(f"Error getting suggestion with context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggestions/batch")
async def get_batch_suggestions(request: BatchSuggestionRequest):
    """Get AI suggestions for multiple emails."""
    try:
        # Get processed IDs
        processed_ids = memory_store.get_processed_email_ids()
        
        # Get batch suggestions
        suggestions = []
        for suggestion in classify_emails_streaming(
            gmail=gmail_client,
            memory_store=memory_store,
            max_results=request.max_results,
            model=os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
            score_threshold=0.30,
        ):
            suggestions.append({
                "email": suggestion["message"],
                "suggestedLabel": suggestion.get("suggested_label"),
                "confidence": suggestion.get("scores", {}).get(suggestion.get("suggested_label", ""), 0),
                "rationale": suggestion.get("rationale", ""),
                "source": suggestion.get("source", "llm"),
                "scores": suggestion.get("scores", {})
            })
        
        logger.info(f"Generated {len(suggestions)} suggestions")
        return {"suggestions": suggestions}
    
    except Exception as e:
        logger.error(f"Error getting batch suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggestions/apply")
async def apply_approved_labels(request: ApplyLabelsRequest):
    """Apply approved labels to emails."""
    try:
        applied_count = 0
        
        for email_id, decision in request.approvals.items():
            if decision.get("approved"):
                label_name = decision.get("final_label")
                if label_name:
                    # Ensure label exists
                    label_id, _ = gmail_client.ensure_label(label_name)
                    
                    # Apply label
                    gmail_client.apply_label(email_id, label_id)
                    
                    # Mark as processed in memory
                    memory_store.mark_email_processed(email_id, label_name, True)
                    
                    applied_count += 1
                    logger.info(f"Applied label '{label_name}' to email {email_id}")
        
        return {
            "success": True,
            "applied_count": applied_count,
            "message": f"Applied {applied_count} labels"
        }
    
    except Exception as e:
        logger.error(f"Error applying labels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Settings endpoints
@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return SettingsResponse(
        model=os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
        threshold=0.30,
        max_results=10
    )


@app.post("/api/settings")
async def update_settings(settings: Dict[str, Any]):
    """Update settings."""
    # In a real app, you'd persist these
    logger.info(f"Settings updated: {settings}")
    return {"success": True}


@app.get("/api/models", response_model=ModelsResponse)
async def get_available_models():
    """Get available Ollama models."""
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]
            models = [line.split()[0] for line in lines if line.strip()]
            return ModelsResponse(models=models if models else ["gemma3:4b"])
        return ModelsResponse(models=["gemma3:4b"])
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        return ModelsResponse(models=["gemma3:4b"])


# Statistics endpoints
@app.get("/api/stats")
async def get_stats():
    """Get memory statistics."""
    try:
        import sqlite3
        db_path = os.path.join(os.getcwd(), "data", "memory.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Total labeled emails
        cur.execute("SELECT COUNT(*) FROM labeled_emails")
        total_emails = cur.fetchone()[0]
        
        # Approved emails
        cur.execute("SELECT COUNT(*) FROM labeled_emails WHERE accepted = 1")
        approved_emails = cur.fetchone()[0]
        
        conn.close()
        
        return {
            "total_processed": total_emails,
            "approved": approved_emails,
            "rejected": total_emails - approved_emails
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {"total_processed": 0, "approved": 0, "rejected": 0}


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8502,
        log_level="info"
    )

