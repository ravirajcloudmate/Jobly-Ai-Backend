# test_evaluation.py - Test script for evaluation system
import asyncio
import json
from evaluator import AnswerEvaluator

async def test_evaluator():
    """Test the answer evaluator with sample questions and answers"""
    
    evaluator = AnswerEvaluator()
    
    print("=" * 80)
    print("🧪 TESTING ANSWER EVALUATOR")
    print("=" * 80)
    
    # Test Case 1: Good answer about SOLID principles
    print("\n📝 Test Case 1: SOLID Principles (Good Answer)")
    print("-" * 80)
    
    evaluation1 = await evaluator.evaluate_answer(
        question="Can you explain the SOLID principles in software engineering?",
        answer="""SOLID is an acronym for five design principles:
        
        1. Single Responsibility Principle - A class should have only one reason to change
        2. Open/Closed Principle - Software entities should be open for extension but closed for modification
        3. Liskov Substitution Principle - Derived classes must be substitutable for their base classes
        4. Interface Segregation Principle - Clients shouldn't be forced to depend on interfaces they don't use
        5. Dependency Inversion Principle - High-level modules shouldn't depend on low-level modules
        
        These principles help create maintainable and scalable code.""",
        expected_keywords=["Single Responsibility", "Open/Closed", "Liskov", "Interface Segregation", "Dependency Inversion"],
        difficulty_level="medium"
    )
    
    print(f"✅ Score: {evaluation1['score']}/10")
    print(f"✅ Correct: {evaluation1['is_correct']}")
    print(f"✅ Feedback: {evaluation1['feedback']}")
    print(f"✅ Strengths: {', '.join(evaluation1['strengths'])}")
    
    # Test Case 2: Weak answer about React hooks
    print("\n📝 Test Case 2: React Hooks (Weak Answer)")
    print("-" * 80)
    
    evaluation2 = await evaluator.evaluate_answer(
        question="What are React hooks and why are they useful?",
        answer="React hooks are functions that let you use state. They are useful.",
        expected_keywords=["useState", "useEffect", "functional components", "lifecycle"],
        difficulty_level="medium"
    )
    
    print(f"✅ Score: {evaluation2['score']}/10")
    print(f"✅ Correct: {evaluation2['is_correct']}")
    print(f"✅ Partial: {evaluation2['is_partial']}")
    print(f"✅ Feedback: {evaluation2['feedback']}")
    print(f"✅ Improvements: {', '.join(evaluation2['improvements'])}")
    
    # Test Case 3: Excellent answer about databases
    print("\n📝 Test Case 3: Database Indexing (Excellent Answer)")
    print("-" * 80)
    
    evaluation3 = await evaluator.evaluate_answer(
        question="How do database indexes improve query performance?",
        answer="""Database indexes improve query performance by creating a separate data structure 
        that stores a subset of the table's data in a sorted manner. This allows the database to 
        quickly locate rows without scanning the entire table.
        
        Indexes work like a book's index - instead of reading every page, you can jump directly to 
        the relevant section. They're particularly effective for:
        - WHERE clause filtering
        - JOIN operations
        - ORDER BY sorting
        
        However, indexes also have trade-offs:
        - They take up additional storage space
        - INSERT/UPDATE/DELETE operations become slower due to index maintenance
        
        Common index types include B-tree, Hash, and Bitmap indexes, each optimized for different use cases.""",
        expected_keywords=["B-tree", "search", "performance", "storage"],
        difficulty_level="medium"
    )
    
    print(f"✅ Score: {evaluation3['score']}/10")
    print(f"✅ Correct: {evaluation3['is_correct']}")
    print(f"✅ Feedback: {evaluation3['feedback']}")
    print(f"✅ Technical Depth: {evaluation3.get('technical_depth', 0)}%")
    print(f"✅ Communication Quality: {evaluation3.get('communication_quality', 0)}%")
    
    # Calculate overall performance
    print("\n" + "=" * 80)
    print("📊 OVERALL PERFORMANCE")
    print("=" * 80)
    
    performance = evaluator.calculate_overall_performance()
    
    print(f"\n📈 Total Score: {performance['total_score']}%")
    print(f"📊 Questions Answered: {performance['total_questions']}")
    print(f"✅ Correct Answers: {performance['correct_answers']}")
    print(f"⚠️  Partial Answers: {performance['partial_answers']}")
    print(f"❌ Wrong Answers: {performance['wrong_answers']}")
    
    print(f"\n💪 Strengths:")
    for strength in performance['strengths']:
        print(f"   • {strength}")
    
    print(f"\n📝 Areas for Improvement:")
    for weakness in performance['weaknesses']:
        print(f"   • {weakness}")
    
    print(f"\n🎯 Recommendation:")
    print(f"   {performance['recommendation']}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_evaluator())



