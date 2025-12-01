# evaluator.py - AI-powered Answer Evaluation Module
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
import openai
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")


class AnswerEvaluator:
    """Evaluates candidate answers using AI/LLM"""

    def __init__(self):
        self.evaluation_history = []

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        expected_keywords: Optional[List[str]] = None,
        difficulty_level: str = "medium",
        context: Optional[str] = None
    ) -> Dict:
        """
        Evaluate candidate's answer using OpenAI GPT-4
        
        Args:
            question: The interview question asked
            answer: The candidate's response
            expected_keywords: List of expected topics/keywords
            difficulty_level: easy, medium, hard
            context: Additional context about the role/position
            
        Returns:
            Dictionary with evaluation results
        """
        try:
            logger.info(f"🔍 Evaluating answer for question: {question[:100]}...")
            
            # Build evaluation prompt
            evaluation_prompt = self._build_evaluation_prompt(
                question=question,
                answer=answer,
                expected_keywords=expected_keywords,
                difficulty_level=difficulty_level,
                context=context
            )
            
            # Call OpenAI API
            response = await self._call_openai(evaluation_prompt)
            
            # Parse and structure the response
            evaluation = self._parse_evaluation_response(response)
            
            # Add metadata
            evaluation["question"] = question
            evaluation["answer"] = answer
            evaluation["timestamp"] = datetime.now().isoformat()
            evaluation["difficulty_level"] = difficulty_level
            
            # Store in history
            self.evaluation_history.append(evaluation)
            
            logger.info(f"✅ Evaluation complete - Score: {evaluation.get('score', 0)}/10")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"❌ Evaluation failed: {e}")
            return self._get_fallback_evaluation(question, answer, expected_keywords)

    def _build_evaluation_prompt(
        self,
        question: str,
        answer: str,
        expected_keywords: Optional[List[str]],
        difficulty_level: str,
        context: Optional[str]
    ) -> str:
        """Build detailed evaluation prompt for GPT-4"""
        
        prompt = f"""You are an expert technical interviewer evaluating a candidate's response.

**Interview Question:**
{question}

**Candidate's Answer:**
{answer}

**Difficulty Level:** {difficulty_level}

{"**Expected Topics/Keywords:** " + ", ".join(expected_keywords) if expected_keywords else ""}

{"**Job Context:** " + context if context else ""}

**Your Task:**
Evaluate this answer comprehensively and provide a detailed assessment in the following JSON format:

{{
  "is_correct": true/false,
  "is_partial": true/false,
  "score": <0-10>,
  "evaluation": {{
    "accuracy": <0-100>,
    "completeness": <0-100>,
    "relevance": <0-100>,
    "confidence": "high/medium/low"
  }},
  "feedback": "Brief constructive feedback (2-3 sentences)",
  "keywords_matched": ["keyword1", "keyword2"],
  "keywords_missed": ["keyword3"],
  "strengths": ["strength1", "strength2"],
  "improvements": ["improvement1", "improvement2"],
  "technical_depth": <0-100>,
  "communication_quality": <0-100>
}}

**Evaluation Criteria:**
1. **Accuracy:** How technically correct is the answer?
2. **Completeness:** Does it cover all important aspects?
3. **Relevance:** Is the answer on-topic and focused?
4. **Technical Depth:** Shows understanding beyond surface level?
5. **Communication:** Clear, structured, and easy to follow?

**Scoring Guide:**
- 9-10: Excellent - Comprehensive, accurate, well-explained
- 7-8: Good - Solid understanding with minor gaps
- 5-6: Average - Basic understanding, missing details
- 3-4: Below Average - Significant gaps or misunderstandings
- 0-2: Poor - Incorrect or off-topic

**Classification:**
- is_correct: true if score >= 7
- is_partial: true if score is 5-6
- is_correct: false if score < 5

Provide ONLY the JSON output, no additional text."""

        return prompt

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API for evaluation"""
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # or gpt-4 for better quality
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert technical interviewer. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent evaluation
                max_tokens=800,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ OpenAI API call failed: {e}")
            raise

    def _parse_evaluation_response(self, response_text: str) -> Dict:
        """Parse and validate OpenAI response"""
        try:
            evaluation = json.loads(response_text)
            
            # Ensure all required fields are present
            required_fields = {
                "is_correct": False,
                "is_partial": False,
                "score": 0,
                "evaluation": {
                    "accuracy": 0,
                    "completeness": 0,
                    "relevance": 0,
                    "confidence": "low"
                },
                "feedback": "",
                "keywords_matched": [],
                "keywords_missed": [],
                "strengths": [],
                "improvements": []
            }
            
            # Merge with defaults
            for key, default_value in required_fields.items():
                if key not in evaluation:
                    evaluation[key] = default_value
            
            # Validate score range
            evaluation["score"] = max(0, min(10, evaluation.get("score", 0)))
            
            return evaluation
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse evaluation JSON: {e}")
            logger.error(f"Response: {response_text}")
            return self._get_fallback_evaluation("", "", [])

    def _get_fallback_evaluation(
        self,
        question: str,
        answer: str,
        expected_keywords: Optional[List[str]] = None
    ) -> Dict:
        """Fallback evaluation using keyword matching when AI fails"""
        logger.warning("⚠️ Using fallback keyword-based evaluation")
        
        if not expected_keywords:
            expected_keywords = []
        
        # Simple keyword matching
        answer_lower = answer.lower()
        matched_keywords = [kw for kw in expected_keywords if kw.lower() in answer_lower]
        missed_keywords = [kw for kw in expected_keywords if kw.lower() not in answer_lower]
        
        # Calculate score based on keyword matches
        if expected_keywords:
            match_ratio = len(matched_keywords) / len(expected_keywords)
            score = round(match_ratio * 10, 1)
        else:
            # If no keywords provided, give moderate score if answer exists
            score = 6.0 if len(answer.strip()) > 20 else 3.0
        
        is_correct = score >= 7
        is_partial = 5 <= score < 7
        
        return {
            "is_correct": is_correct,
            "is_partial": is_partial,
            "score": score,
            "evaluation": {
                "accuracy": int(score * 10),
                "completeness": int(score * 10),
                "relevance": int(score * 10),
                "confidence": "low"
            },
            "feedback": "Automated evaluation based on keyword matching. Manual review recommended.",
            "keywords_matched": matched_keywords,
            "keywords_missed": missed_keywords,
            "strengths": ["Response provided"] if answer else [],
            "improvements": ["Could provide more detailed explanation"] if not is_correct else [],
            "technical_depth": int(score * 10),
            "communication_quality": 70,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
            "fallback": True
        }

    def calculate_overall_performance(self) -> Dict:
        """Calculate overall interview performance from all evaluations"""
        if not self.evaluation_history:
            return {
                "total_score": 0,
                "correct_answers": 0,
                "wrong_answers": 0,
                "partial_answers": 0,
                "average_score": 0,
                "total_questions": 0
            }
        
        total_questions = len(self.evaluation_history)
        correct_answers = sum(1 for e in self.evaluation_history if e.get("is_correct", False))
        partial_answers = sum(1 for e in self.evaluation_history if e.get("is_partial", False))
        wrong_answers = total_questions - correct_answers - partial_answers
        
        # Calculate average score
        total_score_sum = sum(e.get("score", 0) for e in self.evaluation_history)
        average_score = round((total_score_sum / total_questions) * 10, 1) if total_questions > 0 else 0
        
        # Calculate category averages
        avg_accuracy = sum(e.get("evaluation", {}).get("accuracy", 0) for e in self.evaluation_history) / total_questions
        avg_technical = sum(e.get("technical_depth", 0) for e in self.evaluation_history) / total_questions
        avg_communication = sum(e.get("communication_quality", 0) for e in self.evaluation_history) / total_questions
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if avg_communication >= 75:
            strengths.append("Strong communication skills")
        elif avg_communication < 60:
            weaknesses.append("Could improve communication clarity")
        
        if avg_technical >= 75:
            strengths.append("Good technical knowledge")
        elif avg_technical < 60:
            weaknesses.append("Needs to deepen technical understanding")
        
        if avg_accuracy >= 80:
            strengths.append("High accuracy in responses")
        elif avg_accuracy < 60:
            weaknesses.append("Could improve answer accuracy")
        
        # Response rate
        response_rate = (correct_answers + partial_answers) / total_questions * 100 if total_questions > 0 else 0
        
        # Generate recommendation
        if average_score >= 80:
            recommendation = "Strongly recommend for next round. Candidate demonstrates excellent understanding and communication."
        elif average_score >= 65:
            recommendation = "Recommend for next round. Candidate shows good potential with some areas for growth."
        elif average_score >= 50:
            recommendation = "Consider for next round with reservations. Additional assessment may be needed."
        else:
            recommendation = "Does not meet current requirements. May need more preparation."
        
        return {
            "total_score": average_score,
            "correct_answers": correct_answers,
            "wrong_answers": wrong_answers,
            "partial_answers": partial_answers,
            "average_score": average_score,
            "total_questions": total_questions,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendation": recommendation,
            "metrics": {
                "accuracy": round(avg_accuracy, 1),
                "technical_score": round(avg_technical, 1),
                "communication_score": round(avg_communication, 1),
                "response_rate": round(response_rate, 1),
                "confidence_level": round((avg_accuracy + avg_technical) / 2, 1)
            }
        }


# Singleton instance
_evaluator_instance = None


def get_evaluator() -> AnswerEvaluator:
    """Get singleton evaluator instance"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = AnswerEvaluator()
    return _evaluator_instance



