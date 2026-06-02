"""Aurora WebRTC Voice System - Main Application."""
import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import init_db, get_db, User, Conversation, Message, Memory
from redis_client import redis_manager
from ai_engine import ai_engine

# ============ FASTAPI + SOCKET.IO SETUP ============
app = FastAPI(title="Aurora WebRTC Voice System", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO with Redis adapter (for multi-server scaling)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.ALLOWED_ORIGINS,
    logger=settings.DEBUG
)
sio_app = socketio.ASGIApp(sio, app)

# Mount static files (frontend)
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")

@app.get("/api/ice-servers")
async def get_ice_servers():
    """Get STUN/TURN servers for WebRTC."""
    servers = [{"urls": url} for url in settings.STUN_SERVERS]
    if settings.TURN_SERVER:
        servers.append({
            "urls": settings.TURN_SERVER,
            "username": settings.TURN_USERNAME,
            "credential": settings.TURN_PASSWORD
        })
    return {"iceServers": servers}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# ============ SOCKET.IO EVENTS ============

@sio.event
async def connect(sid, environ):
    """Handle new socket connection."""
    print(f"Client connected: {sid}")
    await sio.emit("connected", {"sid": sid, "message": "Welcome to Aurora"}, to=sid)

@sio.event
async def disconnect(sid):
    """Handle disconnection — cleanup sessions."""
    print(f"Client disconnected: {sid}")
    # Find and cleanup any active sessions for this socket
    # (In production, track socket->session mapping in Redis)

@sio.on("join-room")
async def join_room(sid, data):
    """Join a call room."""
    room_id = data.get("room_id", str(uuid.uuid4()))
    user_id = data.get("user_id", f"anonymous_{sid[:8]}")
    persona = data.get("persona", "aurora")

    await sio.enter_room(sid, room_id)
    await redis_manager.join_room(room_id, user_id, sid)

    # Store session mapping
    session_id = str(uuid.uuid4())
    await redis_manager.create_session(session_id, user_id, {
        "room_id": room_id,
        "socket_id": sid,
        "persona": persona,
        "role": "waiting"  # caller or callee
    })

    # Check room occupancy
    members = await redis_manager.get_room_members(room_id)

    await sio.emit("room-joined", {
        "room_id": room_id,
        "session_id": session_id,
        "user_id": user_id,
        "members_count": len(members),
        "is_initiator": len(members) == 1
    }, to=sid)

    # Notify others
    if len(members) > 1:
        await sio.emit("peer-joined", {
            "user_id": user_id,
            "room_id": room_id
        }, room=room_id, skip_sid=sid)
        await redis_manager.update_session_status(session_id, "connecting")

    print(f"User {user_id} joined room {room_id} (members: {len(members)})")

@sio.on("webrtc-offer")
async def handle_offer(sid, data):
    """Relay WebRTC offer to peer."""
    room_id = data.get("room_id")
    offer = data.get("offer")

    # Store offer in Redis for resilience
    session_id = data.get("session_id")
    if session_id:
        await redis_manager.update_session_status(session_id, "connecting")

    await sio.emit("webrtc-offer", {
        "offer": offer,
        "from": sid,
        "session_id": session_id
    }, room=room_id, skip_sid=sid)

    print(f"Offer relayed in room {room_id}")

@sio.on("webrtc-answer")
async def handle_answer(sid, data):
    """Relay WebRTC answer to peer."""
    room_id = data.get("room_id")
    answer = data.get("answer")

    await sio.emit("webrtc-answer", {
        "answer": answer,
        "from": sid
    }, room=room_id, skip_sid=sid)

    # Update session status
    session_id = data.get("session_id")
    if session_id:
        await redis_manager.update_session_status(session_id, "active")

    print(f"Answer relayed in room {room_id}")

@sio.on("ice-candidate")
async def handle_ice_candidate(sid, data):
    """Relay ICE candidate or queue if peer not ready."""
    room_id = data.get("room_id")
    candidate = data.get("candidate")
    session_id = data.get("session_id")

    # Try to relay immediately
    await sio.emit("ice-candidate", {
        "candidate": candidate,
        "from": sid,
        "session_id": session_id
    }, room=room_id, skip_sid=sid)

@sio.on("audio-stream")
async def handle_audio_stream(sid, data):
    """Process incoming audio stream, generate AI response."""
    start_time = time.time()

    session_id = data.get("session_id")
    audio_base64 = data.get("audio")
    room_id = data.get("room_id")

    if not all([session_id, audio_base64]):
        await sio.emit("error", {"message": "Missing session_id or audio"}, to=sid)
        return

    try:
        import base64
        audio_bytes = base64.b64decode(audio_base64)

        # 1. Speech to Text
        await sio.emit("processing", {"stage": "transcribing", "session_id": session_id}, to=sid)
        user_text, confidence = await ai_engine.speech_to_text(audio_bytes, format_hint="webm")

        if not user_text:
            await sio.emit("error", {"message": "Could not understand audio. Please speak clearly."}, to=sid)
            return

        print(f"User said: {user_text} (confidence: {confidence:.2f})")

        # 2. Get memories from database (async - in production)
        # For now, use empty memories
        memories = []

        # 3. Generate AI response
        await sio.emit("processing", {"stage": "thinking", "session_id": session_id}, to=sid)
        ai_text, sentiment, gen_time = await ai_engine.generate_response(session_id, user_text, memories)

        print(f"Aurora replied: {ai_text} (sentiment: {sentiment})")

        # 4. Text to Speech
        await sio.emit("processing", {"stage": "speaking", "session_id": session_id}, to=sid)

        output_path = f"/tmp/aurora_response_{session_id}_{int(time.time())}.mp3"
        tts_success = await ai_engine.text_to_speech(ai_text, output_path)

        if tts_success and os.path.exists(output_path):
            # Read and encode audio
            with open(output_path, "rb") as f:
                response_audio = base64.b64encode(f.read()).decode("utf-8")

            # Send back to client
            await sio.emit("ai-response", {
                "session_id": session_id,
                "user_text": user_text,
                "ai_text": ai_text,
                "sentiment": sentiment,
                "audio": response_audio,
                "processing_time": round(time.time() - start_time, 2)
            }, to=sid)

            # Cleanup
            os.remove(output_path)
        else:
            # Fallback: send text only
            await sio.emit("ai-response", {
                "session_id": session_id,
                "user_text": user_text,
                "ai_text": ai_text,
                "sentiment": sentiment,
                "audio": None,
                "processing_time": round(time.time() - start_time, 2)
            }, to=sid)

        # 5. Extract memories (fire and forget)
        # memories = await ai_engine.extract_memories(user_text, ai_text)
        # Store in DB...

    except Exception as e:
        print(f"Error processing audio: {e}")
        await sio.emit("error", {"message": f"Processing error: {str(e)}"}, to=sid)

@sio.on("text-message")
async def handle_text_message(sid, data):
    """Handle text-only messages (fallback when voice fails)."""
    session_id = data.get("session_id")
    user_text = data.get("text")

    if not user_text:
        return

    ai_text, sentiment, _ = await ai_engine.generate_response(session_id, user_text, [])

    await sio.emit("ai-response", {
        "session_id": session_id,
        "user_text": user_text,
        "ai_text": ai_text,
        "sentiment": sentiment,
        "audio": None
    }, to=sid)

@sio.on("end-call")
async def handle_end_call(sid, data):
    """Cleanup call session."""
    session_id = data.get("session_id")
    room_id = data.get("room_id")

    if session_id:
        await redis_manager.delete_session(session_id)
        ai_engine.clear_session(session_id)

    if room_id:
        await sio.close_room(room_id)

    await sio.emit("call-ended", {"session_id": session_id}, to=sid)
    print(f"Call ended: {session_id}")

# ============ LIFECYCLE ============

@app.on_event("startup")
async def startup():
    await redis_manager.connect()
    await init_db()
    print("🌙 Aurora WebRTC System started")
    print(f"   Redis: {settings.REDIS_URL}")
    print(f"   Database: {settings.DATABASE_URL}")
    print(f"   TTS Engine: {settings.TTS_ENGINE}")

@app.on_event("shutdown")
async def shutdown():
    await redis_manager.disconnect()
    print("Aurora system shutdown")

# Run with: uvicorn main:sio_app --host 0.0.0.0 --port 8000 --reload
