#!/bin/bash
# Quick Start Script for Interview Agent

echo "=================================="
echo "🚀 Starting AI Interview Agent"
echo "=================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with your credentials"
    exit 1
fi

# Load environment variables
export $(cat .env | xargs)

echo ""
echo "=================================="
echo "✅ Environment configured"
echo "📍 LiveKit URL: $LIVEKIT_URL"
echo "🤖 Agent Name: $LIVEKIT_AGENT_NAME"
echo "=================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $AGENT_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Agent Worker in background
echo "🤖 Starting Agent Worker..."
python agent.py dev > agent.log 2>&1 &
AGENT_PID=$!
echo "   Agent PID: $AGENT_PID"

# Wait for agent to start
sleep 3

# Start API Server in background
echo "🌐 Starting API Server..."
python server.py > server.log 2>&1 &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"
echo "   Server URL: http://localhost:8001"

# Wait for server to start
sleep 2

echo ""
echo "=================================="
echo "✅ All services started!"
echo "=================================="
echo ""
echo "📊 Service Status:"
echo "   🤖 Agent Worker: Running (connects to LiveKit)"
echo "   🌐 API Server: http://localhost:8001"
echo "   📝 Health Check: http://localhost:8001/health"
echo ""
echo "📋 Logs:"
echo "   Agent: tail -f agent.log"
echo "   Server: tail -f server.log"
echo ""
echo "🛑 Press Ctrl+C to stop all services"
echo "=================================="
echo ""

# Keep script running
wait