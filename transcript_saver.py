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
    
    logger.debug(f"💬 Added message from {sender}: {text[:50]}...")


# ========================== TRANSCRIPT SAVE FUNCTION ==========================
def save_transcript(interview_id: str = None, room_id: str = None):
    """
    Save the transcript to the backend API via POST request.
    
    Args:
        interview_id: Optional interview ID (will generate UUID if not provided)
        room_id: Optional room ID
    
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
    
    # Get API URL from environment or use default
    api_url = os.getenv(
        "TRANSCRIPT_API_URL",
        "https://your-domain.com/api/interviews/save-transcript"
    )
    
    # Prepare payload
    payload = {
        "interview_id": interview_id,
        "room_id": room_id,
        "transcript": transcript_buffer
    }
    
    try:
        logger.info(f"💾 Saving transcript to {api_url}...")
        logger.info(f"📊 Messages: {len(transcript_buffer)}, Interview ID: {interview_id}")
        
        # Debug: Print final transcript buffer
        print("🧾 FINAL TRANSCRIPT:", transcript_buffer)
        
        res = requests.post(
            api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print("Transcript Save Status:", res.status_code, res.text)
        
        if res.status_code == 200:
            logger.info("✅ Transcript saved successfully!")
            return True
        else:
            logger.error(f"❌ Failed to save transcript: HTTP {res.status_code}")
            logger.error(f"Response: {res.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout while saving transcript")
        print("Transcript Save Status: TIMEOUT")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Could not connect to API at {api_url}")
        print("Transcript Save Status: CONNECTION_ERROR")
        return False
    except Exception as e:
        logger.error(f"❌ Error saving transcript: {e}")
        print(f"Transcript Save Status: ERROR - {e}")
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
            room_id=self.room_id
        )
    
    def get_message_count(self) -> int:
        """Get message count from global buffer"""
        return get_buffer_size()
