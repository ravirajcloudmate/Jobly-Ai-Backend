# agent.py - Interview Agent with Candidate Details (LiveKit 1.2+ API)
import logging
import asyncio
import json
import os
import warnings
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

# Suppress Pydantic warnings from LiveKit's internal models
warnings.filterwarnings("ignore", message=".*conflict with protected namespace.*")


from livekit import agents, rtc
from livekit.agents import Worker, WorkerOptions, AgentSession, Agent
from livekit.plugins import openai, silero

# Import evaluation and tracking modules
from evaluator import AnswerEvaluator, get_evaluator
from livekit_utils import LiveKitMessageSender, InterviewTracker
from transcript_saver import TranscriptSaver, add_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview-agent")
load_dotenv()

# Debug: Environment Variables Check
logger.info("🔍 Environment Variables Check:")
logger.info(f"   LIVEKIT_URL: {os.getenv('LIVEKIT_URL')}")
if os.getenv('LIVEKIT_API_KEY'):
    logger.info(f"   LIVEKIT_API_KEY: {os.getenv('LIVEKIT_API_KEY')[:10]}...")
else:
    logger.info("   LIVEKIT_API_KEY: Not set")
logger.info(f"   LIVEKIT_AGENT_NAME: {os.getenv('LIVEKIT_AGENT_NAME')}")


# ========================== CANDIDATE DETAILS EXTRACTION ==========================
def extract_candidate_details(ctx: agents.JobContext):
    """Extract and log candidate details from metadata"""
    metadata = {}
    candidate_details = {}
    
    logger.info("=" * 80)
    logger.info("🔍 EXTRACTING CANDIDATE DETAILS FROM CONTEXT")
    logger.info("=" * 80)
    
    # DEBUG: Check what's available in ctx
    logger.info(f"📋 ctx has 'job' attribute: {hasattr(ctx, 'job')}")
    if hasattr(ctx, 'job') and ctx.job:
        logger.info(f"📋 ctx.job exists: {ctx.job is not None}")
        logger.info(f"📋 ctx.job has 'metadata' attribute: {hasattr(ctx.job, 'metadata')}")
        if hasattr(ctx.job, 'metadata'):
            logger.info(f"📋 ctx.job.metadata type: {type(ctx.job.metadata)}")
            logger.info(f"📋 ctx.job.metadata value: {ctx.job.metadata}")
    
    # Try to get metadata from ctx.job.metadata (RoomAgentDispatch metadata)
    try:
        if hasattr(ctx, 'job') and ctx.job and hasattr(ctx.job, 'metadata') and ctx.job.metadata:
            logger.info("✅ Found ctx.job.metadata - attempting to parse...")
            metadata = json.loads(ctx.job.metadata) if isinstance(ctx.job.metadata, str) else ctx.job.metadata
            logger.info(f"📦 METADATA FROM ctx.job.metadata:")
            logger.info(f"   Type: {type(metadata)}")
            logger.info(f"   Keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")
            logger.info(f"   Full metadata: {json.dumps(metadata, indent=2)}")
            
            candidate_details = metadata.get("candidateDetails", {})
            if candidate_details:
                logger.info(f"✅ Found candidateDetails in ctx.job.metadata!")
                logger.info(f"   Keys: {list(candidate_details.keys())}")
            else:
                logger.warning("⚠️ candidateDetails key not found in ctx.job.metadata")
                logger.warning(f"   Available keys: {list(metadata.keys())}")
        else:
            logger.warning("⚠️ ctx.job.metadata is empty or not accessible")
    except Exception as e:
        logger.error(f"❌ Error accessing ctx.job.metadata: {e}")
        import traceback
        traceback.print_exc()

    # Fallback to room metadata
    if not candidate_details:
        logger.info("🔄 Trying fallback: ctx.room.metadata...")
        try:
            if ctx.room.metadata:
                logger.info(f"📋 ctx.room.metadata exists: {ctx.room.metadata}")
                room_metadata = json.loads(ctx.room.metadata)
                logger.info(f"📦 METADATA FROM ctx.room.metadata: {json.dumps(room_metadata, indent=2)}")
                candidate_details = room_metadata.get("candidateDetails", {})
                metadata = room_metadata
                if candidate_details:
                    logger.info("✅ Found candidateDetails in ctx.room.metadata!")
            else:
                logger.warning("⚠️ ctx.room.metadata is empty")
        except Exception as e:
            logger.error(f"❌ Error accessing ctx.room.metadata: {e}")
            import traceback
            traceback.print_exc()
    
    
    # Handle nested candidateDetails
    if not candidate_details and "details" in metadata:
        candidate_details = metadata["details"]

    return metadata, candidate_details


# ========================== INTERVIEW STATE ==========================
@dataclass
class InterviewData:
    """Interview data storage with Pydantic compatibility"""
    class Config:
        protected_namespaces = ()  # Fix Pydantic warning
    
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    interview_started: bool = False
    start_time: Optional[datetime] = None
    responses: List[dict] = field(default_factory=list)
    
    # Performance tracking
    evaluator: Optional[AnswerEvaluator] = None
    tracker: Optional[InterviewTracker] = None
    transcript_saver: Optional[TranscriptSaver] = None
    room_instance: Optional[rtc.Room] = None


# ========================== MAIN AGENT CLASS ==========================
class InterviewAgent(Agent):
    """Main Interview Agent with natural conversation flow and performance tracking"""

    def __init__(self, system_prompt: str):
        logger.info("=" * 60)
        logger.info("🤖 InterviewAgent.__init__ called:")
        logger.info(f"   System prompt length: {len(system_prompt)} chars")
        logger.info(f"   System prompt preview: {system_prompt[:200]}...")
        logger.info("=" * 60)
        
        super().__init__(
            instructions=system_prompt,
        )
        
        logger.info("✅ Agent initialized with instructions")
        self.greeting_sent = False
        self.question_count = 0
        self.conversation_active = True
        self.last_question = None
        self.waiting_for_answer = False

    async def on_enter(self) -> None:
        """Called when agent enters conversation"""
        logger.info("🎤 INTERVIEW AGENT ACTIVATED")

        interview_data = self.session.userdata

        if not interview_data.interview_started:
            interview_data.interview_started = True
            interview_data.start_time = datetime.now()
            
            # Initialize evaluator and tracker
            interview_data.evaluator = AnswerEvaluator()
            interview_data.tracker = InterviewTracker()
            
            logger.info("✅ Performance tracking initialized")
            
            # Set up transcript listeners for evaluation
            self._setup_transcript_listeners()

            await asyncio.sleep(0.2)
            await self.greet_candidate()
    
    def _setup_transcript_listeners(self):
        """Set up listeners for user and agent transcripts"""
        # This will be handled in the session setup
        pass
    
    async def on_user_transcript(self, text: str):
        """Handle user transcript - add to buffer"""
        try:
            if text and text.strip():
                add_message("candidate", text)
                print("🟢 USER:", text)
        except Exception as e:
            logger.error(f"❌ Error in on_user_transcript: {e}")
    
    async def on_agent_speech(self, text: str):
        """Handle agent speech - add to buffer"""
        try:
            if text and text.strip():
                add_message("agent", text)
                print("🔵 AGENT:", text)
        except Exception as e:
            logger.error(f"❌ Error in on_agent_speech: {e}")
    
    async def _handle_user_answer(self, answer: str):
        """Handle user's answer and evaluate it"""
        try:
            if not answer or not answer.strip():
                return
                
            interview_data = self.session.userdata
            
            answer = answer.strip()
            logger.info(f"📝 User answered: {answer[:100]}...")
            
            # Add to transcript buffer with print (this calls global add_message)
            await self.on_user_transcript(answer)
            
            # Track the answer
            if interview_data.tracker:
                interview_data.tracker.add_answer(answer)
            
            # If we have a recent question, evaluate the answer
            if self.last_question and interview_data.evaluator:
                logger.info(f"🔍 Evaluating answer to: {self.last_question[:100]}...")
                
                # Perform evaluation
                evaluation = await interview_data.evaluator.evaluate_answer(
                    question=self.last_question,
                    answer=answer,
                    expected_keywords=None,
                    difficulty_level="medium",
                    context=f"Candidate: {interview_data.candidate_name}"
                )
                
                # Send evaluation to frontend via LiveKit data channel
                if interview_data.room_instance:
                    await LiveKitMessageSender.send_answer_evaluation(
                        room=interview_data.room_instance,
                        evaluation=evaluation,
                        question_number=self.question_count
                    )
                    
                    # Also send quick response analysis
                    await LiveKitMessageSender.send_response_analysis(
                        room=interview_data.room_instance,
                        analysis={
                            "is_correct": evaluation.get("is_correct", False),
                            "is_partial": evaluation.get("is_partial", False),
                            "score": evaluation.get("score", 0),
                            "feedback": evaluation.get("feedback", "")
                        }
                    )
                    
                    # Send performance update
                    current_stats = interview_data.tracker.get_current_stats()
                    await LiveKitMessageSender.send_performance_update(
                        room=interview_data.room_instance,
                        current_stats=current_stats
                    )
                
                logger.info(f"✅ Evaluation sent - Score: {evaluation.get('score', 0)}/10")
                logger.info(f"   Correct: {evaluation.get('is_correct', False)}")
                logger.info(f"   Feedback: {evaluation.get('feedback', '')[:100]}...")
                
                # Store response with evaluation
                interview_data.responses.append({
                    "question": self.last_question,
                    "answer": answer,
                    "evaluation": evaluation,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                logger.warning(f"⚠️ No question to evaluate against. Last question: {self.last_question}")
                
        except Exception as e:
            logger.error(f"❌ Error handling user answer: {e}")
            import traceback
            traceback.print_exc()
    
    async def _handle_agent_question(self, question: str):
        """Handle agent's question or statement"""
        try:
            if not question or not question.strip():
                return
                
            interview_data = self.session.userdata
            
            # Add to transcript buffer with print (this calls global add_message)
            await self.on_agent_speech(question.strip())
            
            # Simple heuristic: if message ends with '?' it's likely a question
            if question.strip().endswith('?'):
                self.last_question = question.strip()
                self.question_count += 1
                self.waiting_for_answer = True
                
                logger.info(f"❓ Question #{self.question_count} asked: {question[:100]}...")
                
                # Track the question
                if interview_data.tracker:
                    question_num = interview_data.tracker.add_question(question.strip())
                    
                    # Notify frontend
                    if interview_data.room_instance:
                        await LiveKitMessageSender.send_question_asked(
                            room=interview_data.room_instance,
                            question=question.strip(),
                            question_number=question_num
                        )
            
        except Exception as e:
            logger.error(f"❌ Error handling agent question: {e}")
            import traceback
            traceback.print_exc()
    
    async def on_user_message(self, message: agents.ChatMessage) -> None:
        """Called when user sends a chat message - also evaluate"""
        try:
            if message.message:
                text = message.message.strip()
                logger.info(f"💬 User message: {text[:100]}...")
                # Add to transcript buffer
                await self.on_user_transcript(text)
                await self._handle_user_answer(text)
        except Exception as e:
            logger.error(f"❌ Error in user message handler: {e}")
            import traceback
            traceback.print_exc()
    
    async def on_agent_message(self, message: agents.ChatMessage) -> None:
        """Called when agent sends a chat message - track if it's a question"""
        try:
            if message.message:
                text = message.message.strip()
                logger.info(f"💬 Agent chat message: {text[:100]}...")
                # Add to transcript buffer
                await self.on_agent_speech(text)
                await self._handle_agent_question(text)
        except Exception as e:
            logger.error(f"❌ Error in agent message handler: {e}")
            import traceback
            traceback.print_exc()
    
    async def on_speech_committed(self, evt: agents.SpeechCreatedEvent) -> None:
        """Called when agent speech is committed - capture the text"""
        try:
            # Try to get text from the event
            text = None
            if hasattr(evt, 'text') and evt.text:
                text = evt.text.strip()
            elif hasattr(evt, 'transcript') and evt.transcript:
                if hasattr(evt.transcript, 'text'):
                    text = evt.transcript.text.strip()
            
            if text:
                logger.info(f"🎤 Agent speech committed: {text[:100]}...")
                # Add to transcript buffer
                await self.on_agent_speech(text)
                await self._handle_agent_question(text)
        except Exception as e:
            logger.debug(f"⚠️ Error in speech committed handler: {e}")

    async def greet_candidate(self):
        """Greet candidate and start interview with personalized greeting"""
        if self.greeting_sent:
            return

        self.greeting_sent = True

        try:
            interview_data = self.session.userdata
            candidate_name = interview_data.candidate_name or "there"

            logger.info(f"👋 Greeting candidate: {candidate_name}")

            # Generate greeting
            await self.session.generate_reply(
                instructions="Greet the user and offer your assistance."
            )
            
            # Note: The actual greeting text will be captured via on_agent_message
            # or transcript events, so we don't need to manually add it here
            
            logger.info("✅ Conversation started - agent will continue after each response")
        except Exception as e:
            logger.error(f"❌ Error starting conversation: {e}")
            import traceback
            traceback.print_exc()
    
    async def end_interview(self):
        """End interview and send final analytics"""
        try:
            interview_data = self.session.userdata
            
            if not interview_data.evaluator:
                logger.warning("⚠️ No evaluator found, skipping final analytics")
                return
            
            logger.info("🏁 Ending interview and calculating final performance...")
            
            # Calculate overall performance
            performance = interview_data.evaluator.calculate_overall_performance()
            
            # Get transcript
            transcript = interview_data.tracker.get_transcript() if interview_data.tracker else []
            
            # Send to frontend
            if interview_data.room_instance:
                await LiveKitMessageSender.send_interview_complete(
                    room=interview_data.room_instance,
                    performance=performance,
                    transcript=transcript
                )
            
            logger.info("=" * 80)
            logger.info("✅ INTERVIEW COMPLETED")
            logger.info(f"   Total Score: {performance.get('total_score', 0)}%")
            logger.info(f"   Questions: {performance.get('total_questions', 0)}")
            logger.info(f"   Correct: {performance.get('correct_answers', 0)}")
            logger.info(f"   Recommendation: {performance.get('recommendation', 'N/A')}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error ending interview: {e}")
            import traceback
            traceback.print_exc()


# ========================== AGENT WORKER ==========================
# ✅ CRITICAL FIX: Define entrypoint function first (will be passed to WorkerOptions)
async def entrypoint(ctx: agents.JobContext):
    """Agent entry point - handles RTC sessions"""
    logger.info("=" * 60)
    logger.info(f"🚀 AGENT ENTRY - Room: {ctx.room.name}")
    logger.info(f"📋 Room Metadata: {ctx.room.metadata}")
    logger.info(f"🔍 Job ID: {ctx.job.id if hasattr(ctx, 'job') and ctx.job else 'N/A'}")
    logger.info("=" * 60)
    
    # Extract candidate details
    metadata, candidate_details = extract_candidate_details(ctx)
    
    # Extract candidate information with fallbacks
    candidate_name = (
        candidate_details.get("candidateName")
        or candidate_details.get("candidate_name")
        or metadata.get("candidateName")
        or "Candidate"
    )

    job_title = (
        candidate_details.get("jobTitle")
        or candidate_details.get("job_title")
        or metadata.get("jobTitle")
        or metadata.get("jobDetails", {}).get("job_title")
        or "Position"
    )

    # Handle candidateSkills properly (string/list)
    candidate_skills = (
        candidate_details.get("candidateSkills")
        or candidate_details.get("candidate_skills")
        or []
    )
    if isinstance(candidate_skills, str):
        candidate_skills = [candidate_skills]
    skills_str = ", ".join(candidate_skills[:5]) if candidate_skills else "General technical skills"

    experience = candidate_details.get("experience", "Not specified")
    candidate_summary = (
        candidate_details.get("candidateSummary")
        or candidate_details.get("candidate_summary")
        or ""
    )
    projects = candidate_details.get("candidateProjects") or candidate_details.get("projects", [])
    resume_analysis = (
        candidate_details.get("resumeAnalysis")
        or candidate_details.get("resume_analysis")
        or {}
    )

    # Get agent prompt
    agent_template = (
        metadata.get("agentPrompt")
        or candidate_details.get("agentPrompt")
        or candidate_details.get("agent_prompt")
        or "You are a professional AI interviewer conducting a job interview."
    )
    
    # Log agent prompt extraction
    logger.info("=" * 60)
    logger.info("📋 AGENT PROMPT EXTRACTION:")
    logger.info(f"   From metadata.agentPrompt: {metadata.get('agentPrompt') is not None}")
    logger.info(f"   From candidate_details.agentPrompt: {candidate_details.get('agentPrompt') is not None}")
    logger.info(f"   From candidate_details.agent_prompt: {candidate_details.get('agent_prompt') is not None}")
    logger.info(f"   Final agent_template length: {len(agent_template)} chars")
    logger.info(f"   Agent template preview: {agent_template[:200]}...")
    logger.info("=" * 60)

    # Build system prompt
    system_prompt = f"""{agent_template}

CANDIDATE INFORMATION:
- Name: {candidate_name}
- Position Applied: {job_title}
- Key Skills: {skills_str}
- Experience: {experience}
{f'- Projects: {json.dumps(projects[:3], ensure_ascii=False)[:200]}...' if projects else ''}
{f'- Resume Summary: {candidate_summary[:300]}...' if candidate_summary else ''}
{f'- Resume Analysis: {json.dumps(resume_analysis, ensure_ascii=False)[:300]}...' if resume_analysis else ''}

INTERVIEW GUIDELINES:
1. Conduct a thorough, professional interview.
2. Ask about background, skills, and experience in detail.
3. Use candidate's actual data above to personalize questions.
4. Always greet by name and reference their job title.
"""

    # Logging
    logger.info("=" * 60)
    logger.info(f"📋 Candidate Name: {candidate_name}")
    logger.info(f"💼 Job Title: {job_title}")
    logger.info(f"🛠️ Skills: {skills_str}")
    logger.info(f"🎯 Agent Template Present: {bool(agent_template)}")
    logger.info("=" * 60)

    # Initialize interview data
    interview_data = InterviewData(
        candidate_id=metadata.get("candidateId")
        or candidate_details.get("candidate_email", ""),
        job_id=metadata.get("jobId") or candidate_details.get("job_id", ""),
        candidate_name=candidate_name,
        candidate_email=candidate_details.get("candidateEmail")
        or candidate_details.get("candidate_email", ""),
        room_instance=ctx.room  # Store room for data channel messages
    )
    
    # Initialize TranscriptSaver
    try:
        invitation_id = metadata.get("invitationId") or metadata.get("invitation_id")
        # Generate a fallback UUID if missing (required by backend)
        if not invitation_id:
            import uuid
            invitation_id = str(uuid.uuid4())
            logger.warning(f"⚠️ No invitation_id found, generated fallback: {invitation_id}")
            
        interview_data.transcript_saver = TranscriptSaver(
            invitation_id=invitation_id,
            room_id=ctx.room.name,
            candidate_email=interview_data.candidate_email or "unknown@example.com",
            candidate_name=interview_data.candidate_name or "Unknown Candidate",
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            company_id=metadata.get("companyId") or metadata.get("company_id"),
            job_id=metadata.get("jobId") or metadata.get("job_id")
        )
        logger.info(f"📝 TranscriptSaver initialized for room: {ctx.room.name}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize TranscriptSaver: {e}")
        import traceback
        traceback.print_exc()

    # Create session with new API
    logger.info("🚀 Creating agent session...")
    try:
        session = AgentSession[InterviewData](
            userdata=interview_data,
            stt="deepgram/nova-2-general",  # Supported by LiveKit Cloud
            llm="openai/gpt-4o-mini",
            tts="cartesia/sonic-3:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",  # Supported by LiveKit Cloud
            vad=silero.VAD.load(),
        )
        logger.info("✅ Agent session created")

        # Create and start agent
        logger.info("=" * 60)
        logger.info("🤖 CREATING INTERVIEW AGENT:")
        logger.info(f"   System prompt length: {len(system_prompt)} chars")
        logger.info(f"   System prompt preview: {system_prompt[:300]}...")
        logger.info("=" * 60)
        
        agent = InterviewAgent(system_prompt=system_prompt)
        logger.info("✅ InterviewAgent created with system prompt")
        logger.info("🚀 Starting agent in room...")
        
        await session.start(
            agent=agent,
            room=ctx.room,
        )
        
        logger.info("✅ SESSION STARTED - Agent is now in the room")
        
        # Set up transcript event listeners using session.on()
        @session.on(agents.UserInputTranscribedEvent)
        def on_user_transcript_event(event: agents.UserInputTranscribedEvent):
            """Handle user transcript events"""
            try:
                if event.transcript.is_final and event.transcript.text.strip():
                    text = event.transcript.text.strip()
                    logger.info(f"📝 User transcript received: {text[:100]}...")
                    # Add to transcript buffer via agent method
                    asyncio.create_task(agent.on_user_transcript(text))
                    # Use asyncio to call async handler
                    asyncio.create_task(agent._handle_user_answer(text))
            except Exception as e:
                logger.error(f"❌ Error in user transcript handler: {e}")
                import traceback
                traceback.print_exc()
        
        # Also listen to agent speech events if available
        try:
            @session.on(agents.SpeechCreatedEvent)
            def on_agent_speech_event(event: agents.SpeechCreatedEvent):
                """Handle agent speech events"""
                try:
                    # SpeechCreatedEvent might have different structure
                    # Check if it has text or transcript
                    text = None
                    if hasattr(event, 'text') and event.text:
                        text = event.text.strip()
                    elif hasattr(event, 'transcript') and event.transcript:
                        if hasattr(event.transcript, 'text'):
                            text = event.transcript.text.strip()
                    
                    if text:
                        logger.info(f"🤖 Agent speech received: {text[:100]}...")
                        # Add to transcript buffer via agent method
                        asyncio.create_task(agent.on_agent_speech(text))
                        asyncio.create_task(agent._handle_agent_question(text))
                except Exception as e:
                    logger.debug(f"⚠️ Error in agent speech handler (may not be needed): {e}")
        except Exception as e:
            logger.debug(f"⚠️ SpeechCreatedEvent not available: {e}")
        
        logger.info("✅ Transcript event listeners registered")
        
        # Monitor conversation history to capture agent messages
        async def monitor_conversation_history():
            """Monitor conversation history to capture agent and user messages"""
            try:
                await asyncio.sleep(3)  # Wait for session to initialize
                
                logger.info("📡 Starting conversation history monitoring...")
                last_message_count = 0
                
                while True:
                    await asyncio.sleep(1)  # Check every second
                    
                    try:
                        interview_data = session.userdata
                        
                        # Try to access conversation history from session
                        if hasattr(session, 'conversation') and session.conversation:
                            messages = session.conversation
                            current_count = len(messages) if hasattr(messages, '__len__') else 0
                            
                            # If new messages, process them
                            if current_count > last_message_count:
                                # Get new messages
                                new_messages = messages[last_message_count:] if hasattr(messages, '__getitem__') else []
                                
                                for msg in new_messages:
                                    try:
                                        # Check if it's a user or agent message
                                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                                            text = str(msg.content).strip() if msg.content else ""
                                            if text:
                                                if msg.role == 'user':
                                                    logger.info(f"📝 Found user message in history: {text[:100]}...")
                                                    await agent._handle_user_answer(text)
                                                elif msg.role == 'assistant' or msg.role == 'agent':
                                                    logger.info(f"🤖 Found agent message in history: {text[:100]}...")
                                                    await agent._handle_agent_question(text)
                                    except Exception as e:
                                        logger.debug(f"Error processing message from history: {e}")
                                
                                last_message_count = current_count
                        
                    except Exception as e:
                        # This is expected if conversation history isn't accessible
                        pass
                        
            except Exception as e:
                logger.debug(f"⚠️ Conversation history monitoring stopped: {e}")
        
        # Start conversation history monitoring (as fallback)
        asyncio.create_task(monitor_conversation_history())
        
        # Wrap session methods to track agent responses
        try:
            # Store original methods
            original_generate = session.generate_reply
            
            async def wrapped_generate(*args, **kwargs):
                """Track agent responses when generating replies"""
                result = await original_generate(*args, **kwargs)
                
                # Try to get the actual response text from result
                try:
                    # Check if result has text/content
                    response_text = None
                    if hasattr(result, 'text'):
                        response_text = result.text
                    elif hasattr(result, 'content'):
                        response_text = result.content
                    elif isinstance(result, str):
                        response_text = result
                    
                    # Also check conversation history for the latest agent message
                    if not response_text and hasattr(session, 'conversation') and session.conversation:
                        # Get last message from conversation
                        try:
                            last_msg = session.conversation[-1] if len(session.conversation) > 0 else None
                            if last_msg and hasattr(last_msg, 'content'):
                                response_text = str(last_msg.content)
                            elif last_msg and hasattr(last_msg, 'text'):
                                response_text = str(last_msg.text)
                        except:
                            pass
                    
                    if response_text and response_text.strip():
                        text = response_text.strip()
                        logger.info(f"💬 Agent generated response: {text[:100]}...")
                        await agent._handle_agent_question(text)
                except Exception as e:
                    logger.debug(f"Could not extract response text: {e}")
                
                return result
            
            # Replace method
            session.generate_reply = wrapped_generate
            
            logger.info("✅ Conversation tracking hooks installed")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not install conversation hooks: {e}")
        
        # Monitor for interview end (when participant disconnects)
        async def monitor_interview():
            """Monitor interview and send final analytics when ended"""
            try:
                # Wait for room to close or all participants to leave
                while True:
                    await asyncio.sleep(5)
                    
                    # Check if any remote participants are still in the room
                    remote_participants = list(ctx.room.remote_participants.values())
                    if len(remote_participants) == 0:
                        logger.info("📡 No more participants in room, ending interview...")
                        # Store interview data before ending
                        try:
                            interview_data = session.userdata
                            if interview_data.evaluator and interview_data.room_instance:
                                performance = interview_data.evaluator.calculate_overall_performance()
                                transcript = interview_data.tracker.get_transcript() if interview_data.tracker else []
                                
                                await LiveKitMessageSender.send_interview_complete(
                                    room=interview_data.room_instance,
                                    performance=performance,
                                    transcript=transcript
                                )
                                
                                # Save final transcript to database
                                if interview_data.transcript_saver:
                                    logger.info("💾 Saving final transcript to database...")
                                    success = interview_data.transcript_saver.save_transcript()
                                    if success:
                                        logger.info("✅ Transcript saved to database successfully")
                                    else:
                                        logger.error("❌ Failed to save transcript to database")
                                
                                logger.info("=" * 80)
                                logger.info("✅ INTERVIEW COMPLETED")
                                logger.info(f"   Total Score: {performance.get('total_score', 0)}%")
                                logger.info(f"   Questions: {performance.get('total_questions', 0)}")
                                logger.info(f"   Correct: {performance.get('correct_answers', 0)}")
                                logger.info("=" * 80)
                        except Exception as e:
                            logger.error(f"❌ Error sending final analytics: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"❌ Error in interview monitor: {e}")
        
        # Start monitoring in background
        asyncio.create_task(monitor_interview())
        
    except Exception as e:
        logger.error(f"❌ Failed to start agent session: {e}")
        import traceback
        traceback.print_exc()
        raise


# ========================== RUN APP ==========================
if __name__ == "__main__":
    # Load environment first (ensure it's loaded)
    load_dotenv()
    
    # Get agent name with fallback
    agent_name = os.getenv("LIVEKIT_AGENT_NAME", "interview")
    
    logger.info("=" * 60)
    logger.info(f"🤖 Starting Agent: {agent_name}")
    logger.info(f"📋 LIVEKIT_AGENT_NAME from env: {os.getenv('LIVEKIT_AGENT_NAME')}")
    logger.info(f"📋 Make sure this matches server's LIVEKIT_AGENT_NAME")
    logger.info(f"🌐 Waiting for job requests from LiveKit...")
    logger.info("=" * 60)
    
    
    try:
        # ✅ FIXED: Create WorkerOptions with entrypoint function and agent_name
        opts = WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=agent_name
        )
        agents.cli.run_app(opts)
    except KeyboardInterrupt:
        logger.info("🛑 Agent stopped by user")
    except Exception as e:
        logger.error(f"❌ Agent failed to start: {e}")
        import traceback
        traceback.print_exc()
        raise

