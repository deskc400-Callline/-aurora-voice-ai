"""Configuration management with environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

    # PostgreSQL
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://aurora:aurora@localhost:5432/aurora_db"
    )

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4")

    # ElevenLabs (optional - falls back to Coqui)
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

    # TTS Engine: "elevenlabs" or "coqui"
    TTS_ENGINE = os.getenv("TTS_ENGINE", "coqui")

    # STT
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

    # WebRTC
    STUN_SERVERS = os.getenv("STUN_SERVERS", "stun:stun.l.google.com:19302").split(",")
    TURN_SERVER = os.getenv("TURN_SERVER", "")
    TURN_USERNAME = os.getenv("TURN_USERNAME", "")
    TURN_PASSWORD = os.getenv("TURN_PASSWORD", "")

    # Session
    SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", 3600))  # 1 hour
    MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", 50))

settings = Settings()
