# livekit_utils.py - LiveKit Data Channel Utilities
import logging
import json
from typing import Dict, Optional
from datetime import datetime
from livekit import rtc

logger = logging.getLogger(__name__)


class LiveKitMessageSender:
    """Utility class for sending structured messages via LiveKit data channel"""

    @staticmethod
    async def send_answer_evaluation(
        room: rtc.Room,
        evaluation: Dict,
        question_number: Optional[int] = None
    ) -> bool:
        """
        Send answer evaluation to frontend via LiveKit data channel
        
        Args:
            room: LiveKit room instance
            evaluation: Evaluation dictionary from AnswerEvaluator
            question_number: Optional question number
            
        Returns:
            bool: Success status
        """
        try:
            message = {
                "type": "answer_evaluation",
                "evaluation": {
                    "is_correct": evaluation.get("is_correct", False),
                    "is_partial": evaluation.get("is_partial", False),
                    "score": evaluation.get("score", 0),
                    "accuracy": evaluation.get("evaluation", {}).get("accuracy", 0),
                    "completeness": evaluation.get("evaluation", {}).get("completeness", 0),
                    "relevance": evaluation.get("evaluation", {}).get("relevance", 0),
                    "confidence": evaluation.get("evaluation", {}).get("confidence", "low"),
                    "feedback": evaluation.get("feedback", ""),
                    "keywords_matched": evaluation.get("keywords_matched", []),
                    "keywords_missed": evaluation.get("keywords_missed", []),
                    "strengths": evaluation.get("strengths", []),
                    "improvements": evaluation.get("improvements", [])
                },
                "timestamp": datetime.now().isoformat()
            }
            
            if question_number is not None:
                message["question_number"] = question_number
            
            logger.info(f"📤 Sending answer evaluation via data channel...")
            logger.info(f"   Score: {evaluation.get('score', 0)}/10")
            logger.info(f"   Correct: {evaluation.get('is_correct', False)}")
            
            await LiveKitMessageSender._send_data_message(room, message)
            
            logger.info("✅ Answer evaluation sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send answer evaluation: {e}")
            return False

    @staticmethod
    async def send_response_analysis(
        room: rtc.Room,
        analysis: Dict
    ) -> bool:
        """
        Send immediate response analysis after each answer
        
        Args:
            room: LiveKit room instance
            analysis: Quick analysis dictionary
            
        Returns:
            bool: Success status
        """
        try:
            message = {
                "type": "response_analysis",
                "analysis": {
                    "is_correct": analysis.get("is_correct", False),
                    "is_partial": analysis.get("is_partial", False),
                    "score": analysis.get("score", 0),
                    "feedback": analysis.get("feedback", "")
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"📤 Sending response analysis...")
            
            await LiveKitMessageSender._send_data_message(room, message)
            
            logger.info("✅ Response analysis sent")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send response analysis: {e}")
            return False

    @staticmethod
    async def send_interview_complete(
        room: rtc.Room,
        performance: Dict,
        transcript: Optional[list] = None
    ) -> bool:
        """
        Send final interview completion data with full analysis
        
        Args:
            room: LiveKit room instance
            performance: Overall performance dictionary
            transcript: Optional conversation transcript
            
        Returns:
            bool: Success status
        """
        try:
            message = {
                "type": "interview_complete",
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
                }),
                "timestamp": datetime.now().isoformat()
            }
            
            if transcript:
                message["transcript"] = transcript
            
            logger.info("=" * 80)
            logger.info("📤 SENDING INTERVIEW COMPLETION DATA")
            logger.info(f"   Total Score: {performance.get('total_score', 0)}%")
            logger.info(f"   Correct: {performance.get('correct_answers', 0)}")
            logger.info(f"   Wrong: {performance.get('wrong_answers', 0)}")
            logger.info(f"   Partial: {performance.get('partial_answers', 0)}")
            logger.info(f"   Total Questions: {performance.get('total_questions', 0)}")
            logger.info(f"   Recommendation: {performance.get('recommendation', 'N/A')}")
            logger.info("=" * 80)
            
            await LiveKitMessageSender._send_data_message(room, message)
            
            logger.info("✅ Interview completion data sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send interview completion: {e}")
            return False

    @staticmethod
    async def send_question_asked(
        room: rtc.Room,
        question: str,
        question_number: int,
        expected_keywords: Optional[list] = None
    ) -> bool:
        """
        Notify frontend when a new question is asked
        
        Args:
            room: LiveKit room instance
            question: The question text
            question_number: Question index
            expected_keywords: Keywords to look for in answer
            
        Returns:
            bool: Success status
        """
        try:
            message = {
                "type": "question_asked",
                "question": question,
                "question_number": question_number,
                "timestamp": datetime.now().isoformat()
            }
            
            if expected_keywords:
                message["expected_keywords"] = expected_keywords
            
            logger.info(f"📤 Sending question notification (#{question_number})...")
            
            await LiveKitMessageSender._send_data_message(room, message)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send question notification: {e}")
            return False

    @staticmethod
    async def send_performance_update(
        room: rtc.Room,
        current_stats: Dict
    ) -> bool:
        """
        Send real-time performance statistics update
        
        Args:
            room: LiveKit room instance
            current_stats: Current performance statistics
            
        Returns:
            bool: Success status
        """
        try:
            message = {
                "type": "performance_update",
                "stats": current_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"📤 Sending performance update...")
            
            await LiveKitMessageSender._send_data_message(room, message)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send performance update: {e}")
            return False

    @staticmethod
    async def _send_data_message(room: rtc.Room, message: Dict) -> None:
        """
        Internal method to send data via LiveKit data channel
        
        Args:
            room: LiveKit room instance
            message: Message dictionary to send
        """
        try:
            # Convert message to JSON
            message_json = json.dumps(message, ensure_ascii=False)
            message_bytes = message_json.encode('utf-8')
            
            # Get local participant
            local_participant = room.local_participant
            
            if not local_participant:
                logger.error("❌ No local participant found in room")
                return
            
            # Send to all participants
            await local_participant.publish_data(
                payload=message_bytes,
                reliable=True,  # Ensure delivery
                topic="interview-events"  # Optional topic for filtering
            )
            
            logger.debug(f"✅ Data message sent: {message.get('type', 'unknown')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send data message: {e}")
            import traceback
            traceback.print_exc()
            raise


class InterviewTracker:
    """Track interview progress and statistics"""
    
    def __init__(self):
        self.questions_asked = 0
        self.answers_received = 0
        self.start_time = datetime.now()
        self.transcript = []
        self.current_question = None
        
    def add_question(self, question: str) -> int:
        """Record a new question"""
        self.questions_asked += 1
        self.current_question = question
        self.transcript.append({
            "type": "question",
            "content": question,
            "number": self.questions_asked,
            "timestamp": datetime.now().isoformat()
        })
        return self.questions_asked
    
    def add_answer(self, answer: str, evaluation: Optional[Dict] = None) -> None:
        """Record a candidate answer"""
        self.answers_received += 1
        entry = {
            "type": "answer",
            "content": answer,
            "question_number": self.questions_asked,
            "timestamp": datetime.now().isoformat()
        }
        
        if evaluation:
            entry["evaluation"] = {
                "score": evaluation.get("score", 0),
                "is_correct": evaluation.get("is_correct", False),
                "is_partial": evaluation.get("is_partial", False)
            }
        
        self.transcript.append(entry)
    
    def get_current_stats(self) -> Dict:
        """Get current interview statistics"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "questions_asked": self.questions_asked,
            "answers_received": self.answers_received,
            "duration_seconds": int(duration),
            "response_rate": round((self.answers_received / self.questions_asked * 100), 1) if self.questions_asked > 0 else 0
        }
    
    def get_transcript(self) -> list:
        """Get full transcript"""
        return self.transcript



