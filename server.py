# server.py - Backend API (Port 8001)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
from datetime import datetime
import os
import asyncio
from dotenv import load_dotenv
from livekit import api

# Import evaluation module
from evaluator import AnswerEvaluator, get_evaluator

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

class AnswerEvaluationRequest(BaseModel):
    room_id: str
    question: str
    answer: str
    candidate_id: Optional[str] = None
    question_number: Optional[int] = None
    expected_keywords: Optional[List[str]] = None
    difficulty_level: str = "medium"

class CompleteInterviewRequest(BaseModel):
    room_id: str
    session_id: Optional[str] = None
    candidate_id: Optional[str] = None

class SessionReportRequest(BaseModel):
    room_id: str
    candidate_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    job_id: Optional[str] = None
    performance: Dict[str, Any]
    transcript: List[Dict[str, Any]]
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    responses: List[Dict[str, Any]] = []

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
        
        
        agent_name = os.getenv("LIVEKIT_AGENT_NAME", "interview")  # ✅ Match .env value
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
        # ✅ ADD: Log first 500 chars of metadata for debugging
        if agent_dispatch.metadata:
            logger.info(f"   - Metadata preview: {agent_dispatch.metadata[:500]}...")
        
        
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

@app.post("/api/evaluate-answer")
async def evaluate_answer(request: AnswerEvaluationRequest):
    """
    Evaluate a candidate's answer to an interview question
    
    This endpoint uses AI to analyze and score the candidate's response.
    The evaluation includes accuracy, completeness, and feedback.
    """
    try:
        logger.info("=" * 80)
        logger.info(f"📝 EVALUATING ANSWER")
        logger.info(f"   Room: {request.room_id}")
        logger.info(f"   Question: {request.question[:100]}...")
        logger.info(f"   Answer length: {len(request.answer)} chars")
        logger.info("=" * 80)
        
        # Get or create evaluator for this session
        evaluator = get_evaluator()
        
        # Perform evaluation
        evaluation = await evaluator.evaluate_answer(
            question=request.question,
            answer=request.answer,
            expected_keywords=request.expected_keywords,
            difficulty_level=request.difficulty_level,
            context=f"Candidate ID: {request.candidate_id}"
        )
        
        logger.info(f"✅ Evaluation complete")
        logger.info(f"   Score: {evaluation.get('score', 0)}/10")
        logger.info(f"   Correct: {evaluation.get('is_correct', False)}")
        logger.info(f"   Partial: {evaluation.get('is_partial', False)}")
        
        return {
            "success": True,
            "evaluation": evaluation,
            "room_id": request.room_id,
            "question_number": request.question_number
        }
        
    except Exception as e:
        logger.error(f"❌ Answer evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/complete-interview")
async def complete_interview(request: CompleteInterviewRequest):
    """
    Complete interview and calculate final performance analytics
    
    This endpoint aggregates all evaluations and provides:
    - Overall score
    - Strengths and weaknesses
    - Detailed metrics
    - Hiring recommendation
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🏁 COMPLETING INTERVIEW")
        logger.info(f"   Room: {request.room_id}")
        logger.info(f"   Session: {request.session_id}")
        logger.info("=" * 80)
        
        # Get evaluator
        evaluator = get_evaluator()
        
        # Calculate overall performance
        performance = evaluator.calculate_overall_performance()
        
        logger.info(f"✅ Performance calculated")
        logger.info(f"   Total Score: {performance.get('total_score', 0)}%")
        logger.info(f"   Total Questions: {performance.get('total_questions', 0)}")
        logger.info(f"   Correct: {performance.get('correct_answers', 0)}")
        logger.info(f"   Wrong: {performance.get('wrong_answers', 0)}")
        logger.info(f"   Partial: {performance.get('partial_answers', 0)}")
        
        return {
            "success": True,
            "room_id": request.room_id,
            "score": performance.get("total_score", 0),
            "performance": {
                "total_score": performance.get("total_score", 0),
                "correct_answers": performance.get("correct_answers", 0),
                "wrong_answers": performance.get("wrong_answers", 0),
                "partial_answers": performance.get("partial_answers", 0),
                "total_questions": performance.get("total_questions", 0),
                "strengths": performance.get("strengths", []),
                "weaknesses": performance.get("weaknesses", []),
                "recommendation": performance.get("recommendation", "")
            },
            "analysis": performance.get("metrics", {
                "accuracy": 0,
                "technical_score": 0,
                "communication_score": 0,
                "response_rate": 0,
                "confidence_level": 0
            })
        }
        
    except Exception as e:
        logger.error(f"❌ Complete interview failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/interview-stats/{room_id}")
async def get_interview_stats(room_id: str):
    """
    Get current interview statistics for a room
    
    Returns real-time stats like questions asked, answers received, etc.
    """
    try:
        # Get evaluator to check current progress
        evaluator = get_evaluator()
        
        if not evaluator.evaluation_history:
            return {
                "room_id": room_id,
                "questions_asked": 0,
                "answers_evaluated": 0,
                "current_score": 0
            }
        
        current_performance = evaluator.calculate_overall_performance()
        
        return {
            "room_id": room_id,
            "questions_asked": current_performance.get("total_questions", 0),
            "answers_evaluated": current_performance.get("total_questions", 0),
            "current_score": current_performance.get("total_score", 0),
            "correct_answers": current_performance.get("correct_answers", 0),
            "wrong_answers": current_performance.get("wrong_answers", 0),
            "partial_answers": current_performance.get("partial_answers", 0)
        }
        
    except Exception as e:
        logger.error(f"❌ Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-session-report")
async def save_session_report(request: SessionReportRequest):
    """
    Save complete session report with transcript and performance
    
    This is called by the agent when the interview ends.
    """
    try:
        logger.info("=" * 80)
        logger.info("💾 SAVING SESSION REPORT")
        logger.info(f"   Room: {request.room_id}")
        logger.info(f"   Candidate: {request.candidate_name}")
        logger.info(f"   Total Score: {request.performance.get('total_score', 0)}%")
        logger.info(f"   Questions: {request.performance.get('total_questions', 0)}")
        logger.info("=" * 80)
        
        # Here you would save to your database
        # Example for MongoDB:
        """
        session_report = {
            "room_id": request.room_id,
            "candidate_id": request.candidate_id,
            "candidate_name": request.candidate_name,
            "candidate_email": request.candidate_email,
            "job_id": request.job_id,
            "performance": request.performance,
            "transcript": request.transcript,
            "responses": request.responses,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "created_at": datetime.now().isoformat()
        }
        
        # Save to MongoDB
        result = await db.session_reports.insert_one(session_report)
        logger.info(f"✅ Session report saved with ID: {result.inserted_id}")
        """
        
        # For now, just log it
        logger.info("=" * 80)
        logger.info("📊 SESSION REPORT:")
        logger.info(f"   Candidate: {request.candidate_name} ({request.candidate_email})")
        logger.info(f"   Performance: {request.performance.get('total_score', 0)}% score")
        logger.info(f"   Correct: {request.performance.get('correct_answers', 0)}")
        logger.info(f"   Wrong: {request.performance.get('wrong_answers', 0)}")
        logger.info(f"   Transcript entries: {len(request.transcript)}")
        logger.info(f"   Evaluated responses: {len(request.responses)}")
        logger.info(f"   Duration: {request.start_time} to {request.end_time}")
        logger.info("=" * 80)
        
        # Store session report in memory (can be moved to database)
        if request.room_id not in active_sessions:
            active_sessions[request.room_id] = {}
        
        active_sessions[request.room_id]['session_report'] = {
            "room_id": request.room_id,
            "candidate_id": request.candidate_id,
            "candidate_name": request.candidate_name,
            "candidate_email": request.candidate_email,
            "job_id": request.job_id,
            "performance": request.performance,
            "transcript": request.transcript,
            "responses": request.responses,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "saved_at": datetime.now().isoformat()
        }
        
        # Notify WebSocket clients if connected
        if request.room_id in active_sessions:
            ws = active_sessions[request.room_id].get('websocket')
            if ws:
                try:
                    await ws.send_json({
                        'type': 'session_complete',
                        'room_id': request.room_id,
                        'performance': request.performance,
                        'message': 'Interview session completed and report saved'
                    })
                    logger.info("✅ WebSocket notification sent to frontend")
                except Exception as e:
                    logger.warning(f"⚠️ Could not send WebSocket notification: {e}")
        
        return {
            "success": True,
            "message": "Session report saved successfully",
            "room_id": request.room_id,
            "saved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Save session report failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session-report/{room_id}")
async def get_session_report(room_id: str):
    """
    Retrieve saved session report for a room
    """
    try:
        # Check in-memory storage first
        if room_id in active_sessions and 'session_report' in active_sessions[room_id]:
            logger.info(f"✅ Found session report for room: {room_id}")
            return {
                "success": True,
                "report": active_sessions[room_id]['session_report']
            }
        
        # Example: Fetch from database
        """
        report = await db.session_reports.find_one({"room_id": room_id})
        if not report:
            raise HTTPException(status_code=404, detail="Session report not found")
        
        # Convert ObjectId to string for JSON serialization
        report["_id"] = str(report["_id"])
        return report
        """
        
        # Not found
        raise HTTPException(status_code=404, detail="Session report not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get session report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "stored_candidates": len(candidate_details_store),
        "server": "Backend API",
        "port": 8001,
        "evaluation_enabled": True
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Backend Server on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")