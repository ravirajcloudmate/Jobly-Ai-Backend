# agent.py - Interview Agent with Candidate Details
import logging
import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import ChatMessage
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview-agent")
load_dotenv()


# ========================== CANDIDATE DETAILS EXTRACTION ==========================
def on_job_start(ctx: JobContext):
    """Extract and log candidate details from metadata"""
    metadata = {}
    try:
        if ctx.room.metadata:
            metadata = json.loads(ctx.room.metadata)
    except Exception as e:
        logger.error(f"❌ Metadata parsing error: {e}")
        return
    
    candidate = metadata.get("candidateDetails", {})
    name = candidate.get("candidateName", "Candidate")
    job_title = candidate.get("jobTitle", "Position")
    skills = candidate.get("candidateSkills", "General technical skills")
    
    if isinstance(skills, list):
        skills = ", ".join(skills[:5]) if skills else "General technical skills"
    elif not isinstance(skills, str):
        skills = "General technical skills"
    
    logger.info(f"📋 Candidate: {name}")
    logger.info(f"💼 Job Title: {job_title}")
    logger.info(f"🛠 Skills: {skills}")


# ========================== INTERVIEW STATE ==========================
@dataclass
class InterviewData:
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    interview_started: bool = False
    start_time: Optional[datetime] = None
    responses: List[dict] = field(default_factory=list)


# ========================== MAIN AGENT CLASS ==========================
class InterviewAgent(Agent):
    """Main Interview Agent with natural conversation flow"""

    def __init__(self, system_prompt: str):
        super().__init__(
            instructions=system_prompt,
            llm=openai.LLM(model="gpt-4o-mini", temperature=0.7),
            tts=openai.TTS(voice="alloy", speed=1.0, model="tts-1"),
        )
        self.greeting_sent = False
        self.question_count = 0
        self.conversation_active = True

    async def on_enter(self) -> None:
        """Called when agent enters conversation"""
        logger.info("🎤 INTERVIEW AGENT ACTIVATED")

        interview_data = self.session.userdata

        if not interview_data.interview_started:
            interview_data.interview_started = True
            interview_data.start_time = datetime.now()

            await asyncio.sleep(0.2)
            await self.greet_candidate()

    async def greet_candidate(self):
        """Greet candidate and start interview with personalized greeting"""
        if self.greeting_sent:
            return

        self.greeting_sent = True

        try:
            interview_data = self.session.userdata
            candidate_name = interview_data.candidate_name or "there"

            logger.info(f"👋 Greeting candidate: {candidate_name}")

            await self.session.generate_reply()
            logger.info("✅ Conversation started - agent will continue after each response")
        except Exception as e:
            logger.error(f"❌ Error starting conversation: {e}")
            import traceback
            traceback.print_exc()

    async def on_user_speech_committed(self, message: ChatMessage):
        """Called when user finishes speaking - respond naturally"""
        logger.info("=" * 60)
        logger.info("💬  CANDIDATE RESPONSE RECEIVED")
        logger.info(f"📝 Response: {message.content[:200]}...")
        logger.info("=" * 60)

        await super().on_user_speech_committed(message)

        if not self.conversation_active:
            logger.warning("⚠️ Conversation not active")
            return

        self.question_count += 1

        try:
            logger.info(f"🤖 Agent generating response (Question #{self.question_count})...")
            await self.session.generate_reply()
            logger.info(f"✅ Agent responded successfully - Question #{self.question_count} asked")
        except Exception as e:
            logger.error(f"❌ Error responding to candidate: {e}")
            import traceback
            traceback.print_exc()

            try:
                logger.info("🔄 Trying fallback response...")
                fallback_text = (
                    "Thank you for sharing that. Can you tell me more about your experience?"
                )
                chat_ctx = self.chat_ctx.copy()
                chat_ctx.add_message(role="assistant", content=fallback_text)
                await self.update_chat_ctx(chat_ctx)
                await self.session.generate_reply()
                logger.info("✅ Fallback response sent")
            except Exception as fallback_error:
                logger.error(f"❌ Fallback also failed: {fallback_error}")


# ========================== ENTRYPOINT (FIXED) ==========================
async def entrypoint(ctx: JobContext):
    """Agent entry point"""
    logger.info("=" * 60)
    logger.info(f"🚀 AGENT ENTRY - Room: {ctx.room.name}")
    logger.info(f"📋 Room Metadata: {ctx.room.metadata}")
    logger.info(f"🔍 Job ID: {ctx.job.id if hasattr(ctx, 'job') and ctx.job else 'N/A'}")
    logger.info("=" * 60)
    
    metadata = {}
    candidate_details = {}

    # Try to get metadata from ctx.job.metadata (RoomAgentDispatch metadata)
    try:
        if hasattr(ctx, 'job') and ctx.job and hasattr(ctx.job, 'metadata') and ctx.job.metadata:
            metadata = json.loads(ctx.job.metadata) if isinstance(ctx.job.metadata, str) else ctx.job.metadata
            logger.info(f"📦 METADATA FROM ctx.job.metadata: {json.dumps(metadata, indent=2)}")
            candidate_details = metadata.get("candidateDetails", {})
    except Exception as e:
        logger.error(f"❌ Error accessing ctx.job.metadata: {e}")

    # Fallback to room metadata
    if not candidate_details:
        try:
            if ctx.room.metadata:
                room_metadata = json.loads(ctx.room.metadata)
                logger.info(f"📦 METADATA FROM ctx.room.metadata: {json.dumps(room_metadata, indent=2)}")
                candidate_details = room_metadata.get("candidateDetails", {})
                metadata = room_metadata
        except Exception as e:
            logger.error(f"❌ Error accessing ctx.room.metadata: {e}")
    
    # Extract and log candidate details
    if candidate_details:
        on_job_start(ctx)

    # ✅ FIX #1: ensure candidateDetails exist even if nested differently
    if not candidate_details and "details" in metadata:
        candidate_details = metadata["details"]

    # ✅ FIX #2: extract correctly using all possible key names
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

    # ✅ FIX #3: handle candidateSkills properly (string/list)
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

    # ✅ FIX #4: agent prompt consistent (agentPrompt key)
    agent_template = (
        metadata.get("agentPrompt")
        or candidate_details.get("agentPrompt")
        or candidate_details.get("agent_prompt")
        or "You are a professional AI interviewer conducting a job interview."
    )

    # ✅ FIX #5: build better prompt using all details
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
3. Use candidate’s actual data above to personalize questions.
4. Always greet by name and reference their job title.
"""

    # 🧩 Logging improved for clarity
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
    )

    # ✅ FIX #6: load VAD for STT
    logger.info("🔧 Loading VAD (required for streaming STT)...")
    try:
        vad_instance = silero.VAD.load()
        logger.info("✅ VAD loaded successfully - streaming STT enabled")
    except Exception as e:
        logger.error(f"❌ VAD load failed: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"VAD is required but failed to load: {e}")

    # Create session
    logger.info("🚀 Creating agent session...")
    try:
        session = AgentSession[InterviewData](
            userdata=interview_data,
            stt=openai.STT(language="en"),
            llm=openai.LLM(model="gpt-4o-mini", temperature=0.7),
            tts=openai.TTS(voice="alloy", speed=1.0, model="tts-1"),
            vad=vad_instance,
        )
        logger.info("✅ Agent session created")

        # Pass the new personalized prompt to agent
        agent = InterviewAgent(system_prompt=system_prompt)
        logger.info("🚀 Starting agent in room...")
        await session.start(agent=agent, room=ctx.room)
        logger.info("✅ SESSION STARTED - Agent is now in the room")
    except Exception as e:
        logger.error(f"❌ Failed to start agent session: {e}")
        import traceback
        traceback.print_exc()
        raise


# ========================== RUN APP ==========================
if __name__ == "__main__":
    agent_name = os.getenv("LIVEKIT_AGENT_NAME", "interview-agent")
    logger.info("=" * 60)
    logger.info(f"🤖 Starting Agent: {agent_name}")
    logger.info(f"📋 Make sure this matches server's LIVEKIT_AGENT_NAME")
    logger.info(f"🌐 Waiting for job requests from LiveKit...")
    logger.info("=" * 60)
    
    try:
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=agent_name))
    except KeyboardInterrupt:
        logger.info("🛑 Agent stopped by user")
    except Exception as e:
        logger.error(f"❌ Agent failed to start: {e}")
        import traceback
        traceback.print_exc()
        raise
