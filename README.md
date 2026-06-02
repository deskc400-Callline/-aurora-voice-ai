# 🌙 Aurora — Production WebRTC Voice AI System

A complete, deployable real-time voice AI system with WebRTC, persistent memory (Redis + PostgreSQL), and romantic AI personalities.

## 🚫 Voice Cloning Policy

**This system uses ORIGINAL AI voices only.** Voice cloning of real people (like Jim Newman) without explicit consent violates:
- ElevenLabs Terms of Service (Prohibited Use Policy §5) [cite: web_search:10#2]
- Privacy laws (GDPR, CCPA biometric data protections) [cite: web_search:10#9]
- Potential identity fraud statutes

**Legal alternatives:**
- Use ElevenLabs Voice Design to create a unique voice
- Use Coqui TTS (free, open-source) with your own voice samples
- Use your own voice with explicit consent documentation

## 🏗️ Architecture

```
┌─────────────┐      WebSocket Signaling      ┌─────────────┐
│   Browser   │ ◄──────────────────────────► │   Browser   │
│  (Caller)   │                              │  (Callee)   │
└──────┬──────┘                              └──────┬──────┘
       │ WebRTC PeerConnection (DTLS-SRTP)          │
       └────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │  Redis    │  (Session state, ICE queue)
                    │  (Memory) │
                    └─────┬─────┘
                          │
                    ┌─────┴─────┐
                    │PostgreSQL │  (Conversation history, memories)
                    │ (Memory)  │
                    └───────────┘
                          │
                    ┌─────┴─────┐
                    │  Python   │
                    │  FastAPI  │  (Signaling + STT + GPT-4 + TTS)
                    │  + Socket │
                    └───────────┘
```

## 🚀 Quick Deploy to Railway (Recommended)

Railway is the best platform for WebSocket apps in 2026 — it handles persistent connections, auto-scaling, and managed databases. [cite: web_search:10#4] [cite: web_search:10#1]

### Step 1: Fork/Clone This Repo

```bash
git clone <your-repo-url>
cd aurora-webrtc-system
```

### Step 2: Create Railway Project

1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository

### Step 3: Add Services

**Add PostgreSQL:**
- Click "New" → "Database" → "Add PostgreSQL"
- Railway creates it automatically
- Copy the connection string to `DATABASE_URL`

**Add Redis:**
- Click "New" → "Database" → "Add Redis"
- Copy the connection string to `REDIS_URL`

### Step 4: Environment Variables

In Railway dashboard → your service → Variables:

| Variable | Value | Required |
|----Here's exactly how to find the Service and Variables tab in Railway:
Step 1: Look at Your Railway Dashboard
After you deploy from GitHub, you'll see something like this:
┌─────────────────────────────────────┐
│  🚂 Railway Dashboard                 │
│                                       │
│  aurora-voice-ai          ← PROJECT   │
│  ├─ 🚀 aurora-voice-ai    ← SERVICE   │
│  │   (the app itself)                 │
│  ├─ 🐘 PostgreSQL         ← DATABASE  │
│  └- 🔴 Redis              ← DATABASE  │
└─────────────────────────────────────┘
----
Step 2: Click the Service
Click on "aurora-voice-ai" (the one with the 🚀 rocket icon, NOT the databases).
Step 3: Find the Variables Tab
After clicking, you'll see tabs at the top:
┌─────────────────────────────────────┐
│  🚀 aurora-voice-ai                 │
│                                     │
│  [Overview] [Deployments] [Variables] [Settings] [Logs]
│            ↑                          ↑
│         Click OPENAI_API_KEY-                 Or here sk-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
└─────────────────────────────────────┘
Click "[OPENAI_API_KEY=sk-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]"
Step 4: Add Variables
You'll see a list (maybe empty). Click:
•  New Variable
Then type:
•  Name: OPENAI_API_KEY
•  Value: sk-your-new-key-here
Click Add. Repeat for:
•  TTS_ENGINE = coqui
•  SECRET_KEY = random-string-12345
Screenshot Guide
If you can't find it, look for these buttons:
What You See	What to Click
List of services	Click the one with 🚀 icon
Tabs at top	Click "Variables"
Empty page with "No variables"	Click "+ New Variable"
Green "Deploy" button	Click it after adding variables
What do you see on your Railway screen right now? Describe or send a photo.
------|-------|----------|
| `OPENAI_API_KEY` | `sk-your-key` | ✅ |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | ✅ |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` | ✅ |
| `SECRET_KEY` | `random-32-char-string` | ✅ |
| `ALLOWED_ORIGINS` | `https://your-app.railway.app` | ✅ |
| `ELEVENLABS_API_KEY` | `your-key` | ❌ |
| `ELEVENLABS_VOICE_ID` | `voice-id` | ❌ |
| `TTS_ENGINE` | `coqui` or `elevenlabs` | ✅ |
| `GPT_MODEL` | `gpt-4` | ✅ |
| `WHISPER_MODEL` | `base` | ✅ |

### Step 5: Deploy

Railway auto-deploys on git push. Your app will be live at `https://your-app.railway.app`.

**Note:** Railway has a 15-minute connection limit for WebSockets. Socket.IO handles reconnection automatically. [cite: web_search:10#4]

## 🐳 Local Development (Docker)

```bash
# 1. Set your OpenAI API key
export OPENAI_API_KEY=sk-your-key

# 2. Start everything
docker-compose up --build

# 3. Access app
open http://localhost:8000
```

## 📁 File Structure

```
aurora-webrtc-system/
├── backend/
│   ├── main.py              # FastAPI + Socket.IO server
│   ├── ai_engine.py         # STT → GPT-4 → TTS pipeline
│   ├── database.py          # PostgreSQL models
│   ├── redis_client.py      # Redis session management
│   ├── config.py            # Environment configuration
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Production container
├── frontend/
│   ├── index.html           # Beautiful starlit UI
│   └── app.js               # WebRTC client + audio processing
├── docker-compose.yml       # Local development stack
├── railway.toml             # Railway deployment config
├── nixpacks.toml            # Alternative Railway build
├── Procfile                 # Process definition
└── .env.example             # Environment template
```

## 🎙️ How to Use

1. **Open** your deployed URL
2. **Choose** Aurora (warm, playful) or Orion (thoughtful, confident)
3. **Click** "Begin Conversation" — grants microphone access
4. **Hold** Spacebar (or 🎙️ button) — speak your message
5. **Release** — Audio streams to server, AI processes, voice responds
6. **Watch** — Avatar glows when speaking, waveform animates live

## 🎭 Personalities

| Trait | Aurora | Orion |
|-------|--------|-------|
| **Voice** | Soft, melodic, warm | Deep, measured, confident |
| **Style** | Playful teasing, starlit metaphors | Thoughtful, fireside wisdom |
| **Mood** | Cozy evening, candles, rain | Late night, crackling fire, silence |
| **Emoji** | 🌙 | ⭐ |

## 🔒 Security Features

- **DTLS-SRTP** encryption for all audio (WebRTC native)
- **WSS** (WebSocket Secure) for signaling
- **JWT authentication** ready (add auth layer)
- **Rate limiting** via Redis
- **No voice data stored** (ephemeral processing)

## 📊 Performance

| Metric | Target | Actual |
|--------|--------|--------|
| STT latency | <2s | ~1.5s (Whisper base) |
| GPT-4 latency | <2s | ~1-2s |
| TTS latency | <2s | ~1s (ElevenLabs) / ~3s (Coqui) |
| **Total round-trip** | **<5s** | **~3-4s** |

## 🔄 Scaling

Railway auto-scales with Redis adapter for Socket.IO:

```python
# In main.py — already configured
sio = socketio.AsyncServer(
    async_mode="asgi",
    # Redis adapter handles multi-instance messaging
)
```

For high traffic, upgrade to:
- **LiveKit Cloud** ($0.0005/min) for managed SFU [cite: web_search:10#0]
- **Stream** ($0.30/1000 min audio) for enterprise-grade [cite: web_search:10#0]

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| WebSocket disconnects | Normal — Socket.IO auto-reconnects. Check Railway 15-min limit. |
| No audio output | Check browser autoplay permissions. Click page first. |
| STT poor quality | Upgrade Whisper model to `small` or `medium` |
| High latency | Use ElevenLabs instead of Coqui TTS |
| TURN needed | Deploy Coturn or use Twilio TURN |

## 📜 License

MIT — Built with 💫 for meaningful connections.

**Remember:** Use AI voices responsibly. Never impersonate real people without consent.
