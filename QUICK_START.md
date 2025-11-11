# 🚀 Quick Start Guide - Backend Server

## ⚡ Quick Start (Windows)

### Option 1: Start Backend Only (Recommended for Testing)
```batch
start-backend.bat
```

### Option 2: Start Agent Only
```batch
start-agent.bat
```

---

## 📋 Setup Steps

### Step 1: Create `.env` File

If you don't have a `.env` file, create one:

```batch
copy .env.example .env
```

Then edit `.env` and add your credentials:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key-here
LIVEKIT_API_SECRET=your-api-secret-here
LIVEKIT_AGENT_NAME=interview-agent

# OpenAI Configuration
OPENAI_API_KEY=your-openai-key-here
```

### Step 2: Install Dependencies

```batch
# Create virtual environment (if not exists)
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install httpx
```

### Step 3: Start Backend Server

**Windows:**
```batch
python server.py
```

**Mac/Linux:**
```bash
python3 server.py
```

**Expected Output:**
```
====================================================================
🚀 Starting Backend Server on port 8001
====================================================================
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8001
```

---

## 🧪 Verify Backend is Running

### Test 1: Health Check
Open browser: http://localhost:8001/health

Should return:
```json
{
  "status": "healthy",
  "active_sessions": 0,
  "agents_ready": 0
}
```

### Test 2: Using curl
```bash
curl http://localhost:8001/health
```

---

## 🔧 Troubleshooting

### ❌ Error: "ModuleNotFoundError: No module named 'fastapi'"
**Fix:**
```batch
pip install -r requirements.txt
```

### ❌ Error: "Address already in use"
**Fix:** Port 8001 is already taken
```batch
REM Find process using port 8001
netstat -ano | findstr :8001

REM Kill the process (replace PID_NUMBER)
taskkill /PID <PID_NUMBER> /F

REM Then restart
python server.py
```

### ❌ Error: "No such file or directory: server.py"
**Fix:** Make sure you're in the backend folder
```batch
cd interview-agent-backend
dir server.py
```

### ❌ Error: ".env file not found"
**Fix:**
```batch
copy .env.example .env
REM Then edit .env and add your credentials
```

---

## 📝 Running Backend and Agent Together

### Windows - Two Terminals:

**Terminal 1 - Backend Server:**
```batch
cd interview-agent-backend
venv\Scripts\activate
python server.py
```

**Terminal 2 - Agent Worker:**
```batch
cd interview-agent-backend
venv\Scripts\activate
python agent.py dev
```

### Mac/Linux - Two Terminals:

**Terminal 1 - Backend Server:**
```bash
cd interview-agent-backend
source venv/bin/activate
python3 server.py
```

**Terminal 2 - Agent Worker:**
```bash
cd interview-agent-backend
source venv/bin/activate
python3 agent.py dev
```

---

## ✅ Success Checklist

- [ ] `.env` file exists with all credentials
- [ ] Virtual environment is activated
- [ ] Dependencies are installed
- [ ] Backend server starts without errors
- [ ] Health check returns `{"status":"healthy"}`
- [ ] No ECONNREFUSED errors in frontend

---

## 🎯 Available Endpoints

- `POST /token` - Generate LiveKit tokens
- `POST /agent/join` - Auto-join agent to room
- `POST /start-interview` - Start interview session
- `POST /api/agent-ready` - Agent ready notification
- `POST /api/candidate-joined` - Candidate join notification
- `GET /api/agent-status/{session_id}` - Check agent status
- `WebSocket /ws/interview/{room_id}` - Interview WebSocket
- `GET /health` - Health check

All endpoints accept requests from `http://localhost:3000` (CORS enabled).

---

## 💡 Pro Tips

1. **Keep backend running:** Don't close the terminal running `server.py`
2. **Check logs:** Watch the terminal for connection logs and errors
3. **Test incrementally:** Start with health check, then test endpoints
4. **Use separate terminals:** Run backend and agent in separate terminals

---

## 📞 Need Help?

1. Check that backend is running: `curl http://localhost:8001/health`
2. Check browser console for errors
3. Check backend terminal logs
4. Verify `.env` file has correct credentials

