import requests
import json
import uuid

# Your API endpoint
API_URL = "http://localhost:3000/api/interviews/save-transcript"

# Generate UUIDs for interview_id and room_id
sample_interview_id = str(uuid.uuid4())
sample_room_id = str(uuid.uuid4())

# Create a sample transcript
payload = {
    "interview_id": sample_interview_id,
    "room_id": sample_room_id,
    "transcript": [
        {
            "sender": "candidate",
            "text": "Hello, I am ready for the interview.",
            "timestamp": 1732727000
        },
        {
            "sender": "agent",
            "text": "Please introduce yourself.",
            "timestamp": 1732727010
        }
    ]
}

print("📤 Sending test transcript to API...")
print("🆔 interview_id:", sample_interview_id)
print("🆔 room_id:", sample_room_id)

try:
    response = requests.post(API_URL, json=payload)
    
    print("\n🔍 Status Code:", response.status_code)
    print("📝 Raw Response:", response.text)

    try:
        print("\n📘 Parsed JSON Response:")
        print(json.dumps(response.json(), indent=2))
    except:
        print("⚠ Could not parse JSON response")

except Exception as e:
    print("❌ Error sending request:", e)
