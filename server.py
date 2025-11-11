# server.py - Backend API (Port 8001)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import logging
from datetime import datetime
import os
import asyncio
from dotenv import load_dotenv
from livekit import api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Interview Agent Backend API",
    description="Backend API for AI Interview Agent",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions and candidate details
active_sessions = {}
agent_status = {}
candidate_details_store = {}
candidate_details_events: dict[str, asyncio.Event] = {}

# ============ LiveKit Configuration =============
load_dotenv()
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

class TokenRequest(BaseModel):
    room: str
    identity: str
    metadata: str | None = None
    candidateDetails: dict | None = None  # Accept candidate details directly in token request

@app.post("/token")
async def generate_token(req: TokenRequest):
    """Generate LiveKit token with full candidate details"""
    try:
        if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
            raise HTTPException(status_code=500, detail="LiveKit env vars missing")

        logger.info("=" * 80)
        logger.info(f"🔑 TOKEN REQUEST RECEIVED")
        logger.info(f"📋 Room: {req.room}")
        logger.info(f"👤 Identity: {req.identity}")
        logger.info(f"📥 Has candidateDetails in request: {bool(req.candidateDetails)}")
        logger.info("=" * 80)
        
        # Parse frontend metadata
        metadata_dict = {}
        if req.metadata:
            try:
                metadata_dict = json.loads(req.metadata)
                logger.info(f"📦 Parsed frontend metadata: {list(metadata_dict.keys())}")
            except json.JSONDecodeError:
                metadata_dict = {"metadata": req.metadata}
        
        # Step 1: Check if candidate details are in request body (NEW - supports both orders)
        room_name = req.room
        candidate_data = None
        
        if req.candidateDetails:
            logger.info("✅ Found candidateDetails in token request body")
            candidate_data = req.candidateDetails
            # Also store it for future use
            candidate_details_store[room_name] = candidate_data
            logger.info(f"💾 Stored candidate details in store for room: {room_name}")
            # Notify any waiting token requests
            event = candidate_details_events.get(room_name)
            if event:
                logger.info("🔔 Notifying waiting token requests from request body data")
                event.set()
                candidate_details_events.pop(room_name, None)
        
        # Step 2: Check store (fallback if not in request body)
        if not candidate_data and room_name in candidate_details_store:
            logger.info(f"✅ Found candidate details in store for room: {room_name}")
            candidate_data = candidate_details_store[room_name]
        
        # Step 2.5: If still no candidate data, wait for candidate details (race condition fix)
        if not candidate_data:
            logger.warning(f"⚠️ Candidate details not found yet for room: {room_name}")
            event = candidate_details_events.get(room_name)
            if not event:
                event = asyncio.Event()
                candidate_details_events[room_name] = event
            try:
                logger.info("⏳ Waiting up to 5 seconds for candidate details to arrive...")
                await asyncio.wait_for(event.wait(), timeout=5)
                candidate_data = candidate_details_store.get(room_name)
                if candidate_data:
                    logger.info("✅ Candidate details arrived during wait")
                else:
                    logger.error("❌ Event signaled but candidate details missing")
            except asyncio.TimeoutError:
                logger.error("⏰ Timed out waiting for candidate details (5s)")
                raise HTTPException(
                    status_code=409,
                    detail="Candidate details not yet available. Ensure /agent/candidate-details is called before /token."
                )
        
        # Step 3: Add candidate details to metadata if found
        if candidate_data:
            logger.info("=" * 80)
            logger.info(f"📋 CANDIDATE DETAILS FOUND:")
            logger.info(f"   👤 Name: {candidate_data.get('candidateName', 'N/A')}")
            logger.info(f"   💼 Job: {candidate_data.get('jobTitle', 'N/A')}")
            logger.info(f"   🛠️ Skills: {candidate_data.get('candidateSkills', 'N/A')}")
            logger.info("=" * 80)
            # Clear pending event if exists
            candidate_details_events.pop(room_name, None)
            # Remove from store after use to avoid stale data
            candidate_details_store.pop(room_name, None)
            
            # Add to metadata
            metadata_dict['candidateDetails'] = candidate_data
            
            # Extract agent template/prompt
            agent_template = (
                candidate_data.get('agentPrompt') or
                candidate_data.get('agent_template') or 
                candidate_data.get('agentTemplate') or 
                candidate_data.get('agent_prompt')
            )
            
            if agent_template:
                # Handle if agentPrompt is a JSON string
                if isinstance(agent_template, str) and agent_template.startswith('{'):
                    try:
                        agent_prompt_obj = json.loads(agent_template)
                        metadata_dict['agentPrompt'] = agent_prompt_obj
                        metadata_dict['agentTemplate'] = agent_prompt_obj
                        metadata_dict['agent_template'] = agent_prompt_obj
                        logger.info(f"✅ Agent template (JSON) added")
                    except:
                        metadata_dict['agentPrompt'] = agent_template
                        metadata_dict['agentTemplate'] = agent_template
                        metadata_dict['agent_template'] = agent_template
                        logger.info(f"✅ Agent template (string) added")
                else:
                    metadata_dict['agentPrompt'] = agent_template
                    metadata_dict['agentTemplate'] = agent_template
                    metadata_dict['agent_template'] = agent_template
                    logger.info(f"✅ Agent template added")
        else:
            logger.warning("=" * 80)
            logger.warning(f"⚠️ NO CANDIDATE DETAILS FOUND!")
            logger.warning(f"⚠️ Room: {room_name}")
            logger.warning(f"⚠️ Store size: {len(candidate_details_store)}")
            logger.warning(f"⚠️ Available rooms: {list(candidate_details_store.keys())}")
            logger.warning("=" * 80)
        
        # Add session context
        if room_name in active_sessions:
            session_data = active_sessions[room_name]
            metadata_dict['sessionId'] = session_data.get('session_id')
            metadata_dict['jobDetails'] = session_data.get('job_details', {})
        
        agent_name = os.getenv("LIVEKIT_AGENT_NAME", "interview-agent")
        logger.info("=" * 80)
        logger.info(f"🤖 DISPATCHING AGENT")
        logger.info(f"   Agent Name: {agent_name}")
        logger.info(f"   Room: {req.room}")
        logger.info(f"   Identity: {req.identity}")
        logger.info(f"   Final metadata keys: {list(metadata_dict.keys())}")
        logger.info(f"   ✅ candidateDetails present: {bool(metadata_dict.get('candidateDetails'))}")
        if metadata_dict.get('candidateDetails'):
            cd = metadata_dict['candidateDetails']
            logger.info(f"   👤 Candidate: {cd.get('candidateName', 'N/A')}")
            logger.info(f"   💼 Job: {cd.get('jobTitle', 'N/A')}")
        logger.info("=" * 80)

        # Generate token with enriched metadata
        # IMPORTANT: RoomAgentDispatch metadata goes to ctx.job.metadata in agent
        agent_metadata_json = json.dumps(metadata_dict, ensure_ascii=False)
        
        logger.info("=" * 80)
        logger.info(f"📤 FINAL METADATA BEING SENT TO AGENT:")
        logger.info(f"   Metadata length: {len(agent_metadata_json)} bytes")
        logger.info(f"   Has candidateDetails: {bool(metadata_dict.get('candidateDetails'))}")
        if metadata_dict.get('candidateDetails'):
            cd = metadata_dict['candidateDetails']
            logger.info(f"   👤 Candidate: {cd.get('candidateName', 'N/A')}")
            logger.info(f"   💼 Job: {cd.get('jobTitle', 'N/A')}")
        logger.info(f"   All keys: {list(metadata_dict.keys())}")
        logger.info("=" * 80)
        
        # Create RoomAgentDispatch configuration
        agent_dispatch = api.RoomAgentDispatch(
            agent_name=agent_name,
            metadata=agent_metadata_json,
        )
        
        logger.info(f"🔧 Agent Dispatch Created:")
        logger.info(f"   - Agent Name: {agent_dispatch.agent_name}")
        logger.info(f"   - Metadata Present: {bool(agent_dispatch.metadata)}")
        logger.info(f"   - Metadata Length: {len(agent_dispatch.metadata) if agent_dispatch.metadata else 0} bytes")
        
        token = (
            api.AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
            .with_identity(req.identity)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=req.room,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    agents=[agent_dispatch]
                )
            )
            .to_jwt()
        )
        
        logger.info(f"✅ Token generated successfully with agent dispatch")
        logger.info(f"📋 Agent '{agent_name}' will be dispatched to room '{req.room}'")
        logger.info("=" * 60)
        return {
            "url": LIVEKIT_URL, 
            "token": token, 
            "identity": req.identity, 
            "room": req.room
        }
        
    except Exception as e:
        logger.error(f"❌ Token generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent-ready")
async def agent_ready(data: dict):
    """Called by agent when it joins the room"""
    session_id = data.get('sessionId')
    room_name = data.get('roomName')
    
    logger.info(f"✅ Agent ready - Session: {session_id}, Room: {room_name}")
    
    agent_status[session_id] = {
        'status': 'ready',
        'room': room_name,
        'joined_at': datetime.now().isoformat()
    }
    
    # Notify WebSocket clients
    if room_name in active_sessions:
        ws = active_sessions[room_name].get('websocket')
        if ws:
            try:
                await ws.send_json({
                    'type': 'agent_joined',
                    'message': 'AI Interviewer has joined',
                    'sessionId': session_id
                })
            except Exception as e:
                logger.error(f"❌ WS notification failed: {e}")
    
    return {"status": "success"}

@app.post("/start-interview")
async def start_interview(data: dict):
    """Initialize interview session"""
    try:
        room_name = data.get('roomName') or data.get('room_name')
        session_id = data.get('sessionId') or f"session_{room_name}"
        
        if not room_name:
            raise HTTPException(status_code=400, detail="Missing roomName")
        
        # Store session data
        active_sessions[room_name] = {
            'session_id': session_id,
            'room_name': room_name,
            'candidate_id': data.get('candidateId'),
            'job_id': data.get('jobId'),
            'started_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        logger.info(f"✅ Interview session started: {session_id}")
        
        return {
            "status": "success",
            "sessionId": session_id,
            "roomName": room_name
        }
        
    except Exception as e:
        logger.error(f"❌ Start interview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agent/candidate-details")
async def store_candidate_details(request: Request):
    """Store candidate details sent from frontend - CRITICAL: Call this BEFORE /token"""
    try:
        logger.info("=" * 80)
        logger.info("📥 RECEIVING CANDIDATE DETAILS")
        logger.info("=" * 80)
        
        data = await request.json()
        room_name = data.get("roomName") or data.get("room_name")
        
        if not room_name:
            logger.error("❌ Missing roomName")
            return JSONResponse(
                status_code=400,
                content={"error": "roomName is required"}
            )

        logger.info(f"📋 Room Name: {room_name}")
        logger.info(f"📦 Data keys received: {list(data.keys())}")
        
        # Store data in memory (can later be moved to Redis/DB)
        candidate_details_store[room_name] = data
        # Notify any waiting /token requests
        event = candidate_details_events.get(room_name)
        if event and not event.is_set():
            logger.info("🔔 Notifying pending token request waiting for candidate details")
            event.set()
            candidate_details_events.pop(room_name, None)

        logger.info("=" * 80)
        logger.info(f"✅ CANDIDATE DETAILS STORED SUCCESSFULLY")
        logger.info(f"   Room: {room_name}")
        logger.info(f"   Candidate: {data.get('candidateName', 'N/A')}")
        logger.info(f"   Job Title: {data.get('jobTitle', 'N/A')}")
        logger.info(f"   Store size: {len(candidate_details_store)}")
        logger.info(f"   All rooms in store: {list(candidate_details_store.keys())}")
        logger.info("=" * 80)

        return {
            "status": "success", 
            "message": "Candidate details stored successfully",
            "roomName": room_name,
            "note": "Now you can call /token endpoint"
        }
    except Exception as e:
        logger.error(f"❌ Error saving candidate details: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/agent/candidate-details/{room_name}")
async def get_candidate_details(room_name: str):
    """Get stored candidate details for a room"""
    if room_name not in candidate_details_store:
        raise HTTPException(status_code=404, detail="Candidate details not found")
    
    return {
        "status": "success",
        "details": candidate_details_store[room_name]
    }

@app.websocket("/ws/interview/{room_id}")
async def interview_websocket(websocket: WebSocket, room_id: str):
    """WebSocket for real-time interview updates"""
    await websocket.accept()
    logger.info(f"✅ WebSocket connected: {room_id}")
    
    try:
        # Store websocket connection
        data = await websocket.receive_json()
        
        if data.get('type') == 'join':
            room_name = data.get('roomName') or room_id
            if room_name in active_sessions:
                active_sessions[room_name]['websocket'] = websocket
            else:
                active_sessions[room_name] = {'websocket': websocket}
        
        # Keep connection alive
        while True:
            data = await websocket.receive_json()
            
            if data.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})
            elif data.get('type') == 'end_interview':
                break
            
    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected: {room_id}")
    finally:
        # Clean up
        for key in list(active_sessions.keys()):
            if active_sessions[key].get('websocket') == websocket:
                if 'websocket' in active_sessions[key]:
                    del active_sessions[key]['websocket']

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "stored_candidates": len(candidate_details_store),
        "server": "Backend API",
        "port": 8001
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Backend Server on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")