"""
Transcript Saver Module for Interview Agent Backend
====================================================

Simple functional approach for saving interview transcripts.
"""

import time
import requests
import uuid
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================== GLOBAL TRANSCRIPT BUFFER ==========================
transcript_buffer = []


# ========================== MESSAGE APPEND FUNCTIONS ==========================
def add_message(sender: str, text: str):
    """
    Add a message to the global transcript buffer.
    
    Args:
        sender: "candidate" or "agent"
        text: The message text
    """
    if not text or not text.strip():
        logger.warning("⚠️ Attempted to add empty message, skipping")
        return
    
    transcript_buffer.append({
        "sender": sender,
        "text": text.strip(),
        "timestamp": time.time()
    })
    
    logger.info(f"💬 Transcript: [{sender}] {text[:100]}{'...' if len(text) > 100 else ''}")
    logger.debug(f"📊 Buffer size: {len(transcript_buffer)} messages")


# ========================== TRANSCRIPT SAVE FUNCTION ==========================
def save_transcript(interview_id: str = None, room_id: str = None, frontend_url: str = None):
    """
    Save the transcript to the backend API via POST request.
    
    Args:
        interview_id: Optional interview ID (will generate UUID if not provided)
        room_id: Optional room ID
        frontend_url: Frontend URL to send the transcript to (defaults to env var or localhost)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not transcript_buffer:
        logger.warning("⚠️ No messages in transcript buffer to save")
        return False
    
    # Generate interview_id if not provided
    if not interview_id:
        interview_id = str(uuid.uuid4())
        logger.info(f"📝 Generated interview_id: {interview_id}")
    
    # Get API URL - use provided frontend_url, then env var, then default
    if frontend_url:
        base_url = frontend_url.rstrip('/')
    else:
        base_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip('/')
    
    api_url = f"{base_url}/api/interviews/save-transcript"
    
    # Prepare payload
    payload = {
        "interview_id": interview_id,
        "room_id": room_id,
        "transcript": transcript_buffer
    }
    
    try:
        logger.info("=" * 80)
        logger.info(f"💾 SAVING TRANSCRIPT TO NEXT.JS API")
        logger.info(f"   API URL: {api_url}")
        logger.info(f"   Interview ID: {interview_id}")
        logger.info(f"   Room ID: {room_id}")
        logger.info(f"   Total Messages: {len(transcript_buffer)}")
        logger.info("=" * 80)
        
        # Debug: Print final transcript buffer
        logger.debug(f"🧾 Transcript preview (first 3 messages):")
        for i, msg in enumerate(transcript_buffer[:3]):
            logger.debug(f"   [{i+1}] {msg['sender']}: {msg['text'][:50]}...")
        
        res = requests.post(
            api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        logger.info(f"📡 API Response: HTTP {res.status_code}")
        
        if res.status_code == 200:
            logger.info("=" * 80)
            logger.info("✅ TRANSCRIPT SAVED SUCCESSFULLY!")
            logger.info(f"   Interview ID: {interview_id}")
            logger.info(f"   Room ID: {room_id}")
            logger.info(f"   Messages sent: {len(transcript_buffer)}")
            logger.info("=" * 80)
            # Clear buffer after successful save to prepare for next interview
            clear_buffer()
            return True
        else:
            logger.error("=" * 80)
            logger.error(f"❌ FAILED TO SAVE TRANSCRIPT: HTTP {res.status_code}")
            logger.error(f"   Response: {res.text}")
            logger.error("=" * 80)
            return False
            
    except requests.exceptions.Timeout:
        logger.error("=" * 80)
        logger.error("❌ TIMEOUT WHILE SAVING TRANSCRIPT")
        logger.error(f"   API URL: {api_url}")
        logger.error("=" * 80)
        return False
    except requests.exceptions.ConnectionError:
        logger.error("=" * 80)
        logger.error(f"❌ CONNECTION ERROR: Could not connect to API")
        logger.error(f"   API URL: {api_url}")
        logger.error("   Please check if the Next.js API is running")
        logger.error("=" * 80)
        return False
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERROR SAVING TRANSCRIPT: {e}")
        logger.error(f"   API URL: {api_url}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        return False


# ========================== HELPER FUNCTIONS ==========================
def clear_buffer():
    """Clear the global transcript buffer"""
    global transcript_buffer
    transcript_buffer = []
    logger.info("🧹 Transcript buffer cleared")


def get_buffer_size() -> int:
    """Get the number of messages in the buffer"""
    return len(transcript_buffer)


def get_transcript() -> list:
    """
    Get the current transcript buffer.
    
    Returns:
        list: List of message dictionaries with sender, text, and timestamp
    """
    return transcript_buffer.copy()


# ========================== BACKWARD COMPATIBILITY ==========================
# Keep the class-based approach for existing code that uses TranscriptSaver
class TranscriptSaver:
    """
    Class-based wrapper for backward compatibility.
    Uses the global transcript_buffer internally.
    """
    
    def __init__(
        self,
        invitation_id: str = None,
        room_id: str = None,
        candidate_email: str = None,
        candidate_name: str = None,
        frontend_url: str = "http://localhost:3001",
        company_id: str = None,
        job_id: str = None
    ):
        self.invitation_id = invitation_id
        self.room_id = room_id
        self.candidate_email = candidate_email
        self.candidate_name = candidate_name
        self.company_id = company_id
        self.job_id = job_id
        self.frontend_url = frontend_url.rstrip('/')
        logger.info(f"📝 TranscriptSaver initialized for room: {room_id}")
    
    def add_message(self, speaker: str, text: str, timestamp: str = None):
        """Add message using the global function"""
        add_message(speaker, text)
    
    def save_transcript(self, auto_save: bool = False) -> bool:
        """Save transcript using the global function"""
        return save_transcript(
            interview_id=self.invitation_id,
            room_id=self.room_id,
            frontend_url=self.frontend_url
        )
    
    def get_message_count(self) -> int:
        """Get message count from global buffer"""
        return get_buffer_size()
