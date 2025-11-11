# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from typing import Dict
import json
import logging
from livekit.agents import JobContext

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active interview sessions
active_sessions: Dict[str, dict] = {}

class AIInterviewer:
    def __init__(self, agent_prompt: str, job_details: dict):
        self.agent_prompt = agent_prompt
        self.job_details = job_details
        self.conversation_history = []
        self.current_question_index = 0
        
    async def generate_question(self, previous_answer: str = None):
        """Generate next interview question using OpenAI"""
        
        messages = [
            {"role": "system", "content": self.agent_prompt},
            {"role": "system", "content": f"Job Details: {json.dumps(self.job_details)}"}
        ]
        
        # Add conversation history
        for msg in self.conversation_history:
            messages.append(msg)
            
        if previous_answer:
            messages.append({"role": "user", "content": previous_answer})
        
        # Generate next question
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )
        
        question = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": question})
        
        return question

@app.websocket("/ws/interview/{room_id}")
async def interview_websocket(websocket: WebSocket, room_id: str):
    await websocket.accept()
    
    try:
        # Receive initial join message
        data = await websocket.receive_json()
        
        if data['type'] == 'join' and data['role'] == 'candidate':
            session_id = data['sessionId']
            
            # Fetch session details from database
            session_data = await get_session_from_db(session_id)
            
            # Initialize AI Agent
            ai_agent = AIInterviewer(
                agent_prompt=session_data['agent_prompt'],
                job_details=session_data['job_details']
            )
            
            active_sessions[room_id] = {
                'websocket': websocket,
                'ai_agent': ai_agent,
                'session_id': session_id
            }
            
            # Notify candidate that agent joined
            await websocket.send_json({
                'type': 'agent_joined',
                'message': 'AI Interviewer has joined'
            })
            
            # Start interview with first question
            first_question = await ai_agent.generate_question()
            
            await websocket.send_json({
                'type': 'agent_question',
                'question': first_question,
                'audioUrl': None  # Optional: generate TTS audio
            })
            
        # Main message loop
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'candidate_response':
                # Process candidate's answer
                answer = data['answer']
                
                # Save transcript
                await save_transcript(session_id, 'candidate', answer)
                
                # Generate next question
                next_question = await ai_agent.generate_question(answer)
                
                await websocket.send_json({
                    'type': 'agent_question',
                    'question': next_question
                })
                
            elif data['type'] == 'end_interview':
                # Analyze interview and save results
                analysis = await analyze_interview(ai_agent.conversation_history)
                
                await websocket.send_json({
                    'type': 'interview_complete',
                    'analysis': analysis
                })
                
                break
                
    except WebSocketDisconnect:
        if room_id in active_sessions:
            del active_sessions[room_id]
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

# main.py - Update entrypoint
async def entrypoint(ctx: JobContext):
    logger.info("="*80)
    logger.info("🚀 LIVEKIT AGENT ENTRY POINT")
    logger.info(f"📍 Room: {ctx.room.name}")
    logger.info(f"📋 Metadata: {ctx.room.metadata}")
    logger.info("="*80)
    
    # Parse metadata
    metadata = {}
    try:
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
    except:
        pass
    
    # ... rest of your code

async def get_session_from_db(session_id: str):
    """Fetch session details from Supabase"""
    # Make API call to Next.js backend or directly to Supabase
    # Return session data including agent_prompt and job_details
    pass

async def save_transcript(session_id: str, speaker: str, text: str):
    """Save message to database"""
    # Insert into interview_messages table
    pass

async def analyze_interview(conversation_history: list):
    """Analyze entire interview and provide assessment"""
    
    analysis_prompt = """
    Analyze the following interview conversation and provide:
    1. Overall assessment score (0-100)
    2. Key strengths
    3. Areas for improvement
    4. Specific feedback on answers
    5. Hiring recommendation
    
    Conversation:
    """ + json.dumps(conversation_history)
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": analysis_prompt}],
        max_tokens=500
    )
    
    return response.choices[0].message.content

@app.post("/api/candidate-joined")
async def candidate_joined(data: dict):
    """Endpoint called when candidate joins interview"""
    session_id = data['sessionId']
    # Initialize AI agent for this session
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)