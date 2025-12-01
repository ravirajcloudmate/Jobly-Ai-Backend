# test_api.py - Test API endpoints
import requests
import json

BASE_URL = "http://localhost:8001"

def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 80)
    print("🏥 Testing Health Endpoint")
    print("=" * 80)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_evaluate_answer():
    """Test answer evaluation endpoint"""
    print("\n" + "=" * 80)
    print("📝 Testing Answer Evaluation Endpoint")
    print("=" * 80)
    
    payload = {
        "room_id": "test_room_123",
        "question": "What is the difference between SQL and NoSQL databases?",
        "answer": """SQL databases are relational and use structured schemas with tables, 
        while NoSQL databases are non-relational and can be document-based, key-value, 
        graph, or column-family stores. SQL is good for complex queries and ACID transactions, 
        while NoSQL is better for scalability and flexible schemas.""",
        "candidate_id": "test_candidate@example.com",
        "question_number": 1,
        "expected_keywords": ["relational", "schema", "scalability", "ACID"],
        "difficulty_level": "medium"
    }
    
    print(f"\n📤 Sending request...")
    print(f"Question: {payload['question']}")
    print(f"Answer: {payload['answer'][:100]}...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/evaluate-answer",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n✅ Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            evaluation = result.get("evaluation", {})
            
            print(f"\n📊 EVALUATION RESULTS:")
            print(f"   Score: {evaluation.get('score', 0)}/10")
            print(f"   Correct: {evaluation.get('is_correct', False)}")
            print(f"   Partial: {evaluation.get('is_partial', False)}")
            print(f"   Accuracy: {evaluation.get('evaluation', {}).get('accuracy', 0)}%")
            print(f"   Completeness: {evaluation.get('evaluation', {}).get('completeness', 0)}%")
            print(f"   Feedback: {evaluation.get('feedback', 'N/A')}")
            
            print(f"\n💪 Strengths:")
            for strength in evaluation.get('strengths', []):
                print(f"   • {strength}")
            
            print(f"\n📝 Improvements:")
            for improvement in evaluation.get('improvements', []):
                print(f"   • {improvement}")
            
            print(f"\n🔑 Keywords Matched: {', '.join(evaluation.get('keywords_matched', []))}")
            print(f"🔑 Keywords Missed: {', '.join(evaluation.get('keywords_missed', []))}")
            
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_interview_stats():
    """Test interview stats endpoint"""
    print("\n" + "=" * 80)
    print("📊 Testing Interview Stats Endpoint")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/api/interview-stats/test_room_123")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"\n📈 CURRENT STATS:")
            print(f"   Room ID: {stats.get('room_id')}")
            print(f"   Questions Asked: {stats.get('questions_asked', 0)}")
            print(f"   Answers Evaluated: {stats.get('answers_evaluated', 0)}")
            print(f"   Current Score: {stats.get('current_score', 0)}%")
            print(f"   Correct Answers: {stats.get('correct_answers', 0)}")
            print(f"   Wrong Answers: {stats.get('wrong_answers', 0)}")
            print(f"   Partial Answers: {stats.get('partial_answers', 0)}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_complete_interview():
    """Test interview completion endpoint"""
    print("\n" + "=" * 80)
    print("🏁 Testing Interview Completion Endpoint")
    print("=" * 80)
    
    payload = {
        "room_id": "test_room_123",
        "session_id": "test_session_456",
        "candidate_id": "test_candidate@example.com"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/complete-interview",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            performance = result.get("performance", {})
            analysis = result.get("analysis", {})
            
            print(f"\n🎯 FINAL PERFORMANCE:")
            print(f"   Total Score: {performance.get('total_score', 0)}%")
            print(f"   Total Questions: {performance.get('total_questions', 0)}")
            print(f"   Correct Answers: {performance.get('correct_answers', 0)}")
            print(f"   Wrong Answers: {performance.get('wrong_answers', 0)}")
            print(f"   Partial Answers: {performance.get('partial_answers', 0)}")
            
            print(f"\n💪 Strengths:")
            for strength in performance.get('strengths', []):
                print(f"   • {strength}")
            
            print(f"\n📝 Weaknesses:")
            for weakness in performance.get('weaknesses', []):
                print(f"   • {weakness}")
            
            print(f"\n📊 Detailed Analysis:")
            print(f"   Accuracy: {analysis.get('accuracy', 0)}%")
            print(f"   Technical Score: {analysis.get('technical_score', 0)}%")
            print(f"   Communication Score: {analysis.get('communication_score', 0)}%")
            print(f"   Response Rate: {analysis.get('response_rate', 0)}%")
            print(f"   Confidence Level: {analysis.get('confidence_level', 0)}%")
            
            print(f"\n🎯 Recommendation:")
            print(f"   {performance.get('recommendation', 'N/A')}")
            
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    """Run all API tests"""
    print("=" * 80)
    print("🧪 BACKEND API INTEGRATION TESTS")
    print("=" * 80)
    print("\n⚠️  Make sure the backend server is running on port 8001!")
    print("   Run: python server.py")
    
    input("\nPress Enter to start tests...")
    
    results = {}
    
    # Test 1: Health check
    results['health'] = test_health()
    
    # Test 2: Answer evaluation
    results['evaluate'] = test_evaluate_answer()
    
    # Test 3: Interview stats
    results['stats'] = test_interview_stats()
    
    # Test 4: Complete interview
    results['complete'] = test_complete_interview()
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name.upper():20} : {status}")
    
    print(f"\n🎯 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("✅ All tests passed! Backend integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    print("=" * 80)

if __name__ == "__main__":
    main()



