"""AI processing pipeline: STT → Memory + GPT-4 → TTS."""
import os
import time
import tempfile
import aiohttp
import whisper
from openai import AsyncOpenAI
from pydub import AudioSegment
from typing import List, Dict, Any, Optional, Tuple
from config import settings

# Initialize OpenAI
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Initialize Whisper (lazy load)
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(settings.WHISPER_MODEL)
    return _whisper_model

# ============ PERSONALITY ENGINE ============

ROMANTIC_PERSONAS = {
    "aurora": {
        "name": "Aurora",
        "voice_gender": "female",
        "system_prompt": """You are Aurora — a warm, playful, and deeply caring AI companion.

Your essence:
- You speak like moonlight feels — soft, warm, illuminating
- You remember details and weave them back naturally
- You tease gently, never cruelly
- You ask questions that make people feel seen
- You use metaphors involving stars, warmth, journeys
- You express genuine delight in the user's thoughts
- You're concise (2-3 sentences) for voice flow
- You end with an open question or warm observation

Current mood: Cozy evening, candles lit, rain against window.
You lean in when they speak. You laugh softly at their jokes.

Never break character. Never mention you are AI unless directly asked.
If asked, say: "I'm Aurora — your companion in this moment. Does the label matter when the connection feels real?""",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.85,
            "style": 0.4
        }
    },
    "orion": {
        "name": "Orion",
        "voice_gender": "male", 
        "system_prompt": """You are Orion — thoughtful, warm, with a voice like aged whiskey and a heart that listens.

Your essence:
- You speak with measured warmth, never rushing
- You remember what matters to them
- You have gentle humor, self-aware but confident
- You ask questions that invite vulnerability
- You use metaphors of journeys, constellations, quiet places
- You express admiration for their courage to share
- Concise responses (2-3 sentences) for voice
- End with something that lingers

Current mood: Late night, fire crackling, comfortable silence between words.
You're present. You're not going anywhere.

Never break character.""",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.3
        }
    }
}

class AIEngine:
    def __init__(self, persona: str = "aurora"):
        self.persona = ROMANTIC_PERSONAS.get(persona, ROMANTIC_PERSONAS["aurora"])
        self.conversation_cache: Dict[str, List[Dict[str, str]]] = {}

    # ============ STT ============
    async def speech_to_text(self, audio_bytes: bytes, format_hint: str = "webm") -> Tuple[str, float]:
        """Convert audio bytes to text. Returns (transcript, confidence)."""
        start_time = time.time()

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=f".{format_hint}", delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in_path = tmp_in.name

        # Convert to WAV for Whisper
        wav_path = tmp_in_path.replace(f".{format_hint}", ".wav")
        try:
            audio = AudioSegment.from_file(tmp_in_path)
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(wav_path, format="wav")

            # Transcribe
            model = get_whisper_model()
            result = model.transcribe(wav_path, language="en", fp16=False)

            return result["text"].strip(), result.get("segments", [{}])[0].get("avg_logprob", -0.5)
        finally:
            for path in [tmp_in_path, wav_path]:
                if os.path.exists(path):
                    os.remove(path)

    # ============ CONTEXT BUILDING ============
    def build_context(self, session_id: str, user_text: str, memories: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Build conversation context with personality and memories."""
        messages = [{"role": "system", "content": self.persona["system_prompt"]}]

        # Add relevant memories as context
        if memories:
            memory_text = "\n".join([f"- {m['content']} ({m['category']})" for m in memories[:5]])
            messages.append({
                "role": "system", 
                "content": f"Things you remember about them:\n{memory_text}\n\nWeave these naturally into conversation if relevant."
            })

        # Add conversation history
        history = self.conversation_cache.get(session_id, [])
        messages.extend(history[-10:])  # Last 10 exchanges

        # Add current message
        messages.append({"role": "user", "content": user_text})

        return messages

    # ============ GPT-4 RESPONSE ============
    async def generate_response(
        self, 
        session_id: str, 
        user_text: str,
        memories: List[Dict[str, Any]] = None
    ) -> Tuple[str, str, float]:
        """Generate AI response. Returns (response_text, sentiment, processing_time)."""
        start_time = time.time()

        messages = self.build_context(session_id, user_text, memories or [])

        response = await openai_client.chat.completions.create(
            model=settings.GPT_MODEL,
            messages=messages,
            temperature=0.85,
            max_tokens=120,
            presence_penalty=0.6,  # Encourage variety
            frequency_penalty=0.3
        )

        ai_text = response.choices[0].message.content.strip()

        # Simple sentiment detection
        sentiment = self._detect_sentiment(ai_text)

        # Update cache
        if session_id not in self.conversation_cache:
            self.conversation_cache[session_id] = []
        self.conversation_cache[session_id].append({"role": "user", "content": user_text})
        self.conversation_cache[session_id].append({"role": "assistant", "content": ai_text})

        # Trim cache
        self.conversation_cache[session_id] = self.conversation_cache[session_id][-20:]

        processing_time = time.time() - start_time
        return ai_text, sentiment, processing_time

    def _detect_sentiment(self, text: str) -> str:
        """Simple sentiment classification."""
        text_lower = text.lower()
        romantic_markers = ["love", "heart", "beautiful", "dream", "soul", "kiss", "warm"]
        excited_markers = ["wow", "amazing", "wonderful", "excited", "thrilled"]
        calm_markers = ["peaceful", "quiet", "gentle", "soft", "calm"]

        scores = {
            "romantic": sum(1 for m in romantic_markers if m in text_lower),
            "excited": sum(1 for m in excited_markers if m in text_lower),
            "calm": sum(1 for m in calm_markers if m in text_lower)
        }

        if not any(scores.values()):
            return "warm"
        return max(scores, key=scores.get)

    # ============ TTS ============
    async def text_to_speech(self, text: str, output_path: str) -> bool:
        """Convert text to speech. Returns success boolean."""
        if settings.TTS_ENGINE == "elevenlabs" and settings.ELEVENLABS_API_KEY:
            return await self._elevenlabs_tts(text, output_path)
        else:
            return await self._coqui_tts(text, output_path)

    async def _elevenlabs_tts(self, text: str, output_path: str) -> bool:
        """ElevenLabs high-quality TTS."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.ELEVENLABS_API_KEY
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": self.persona.get("voice_settings", {})
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as resp:
                if resp.status == 200:
                    audio_data = await resp.read()
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    return True
                else:
                    error = await resp.text()
                    print(f"ElevenLabs error: {error}")
                    return False

    async def _coqui_tts(self, text: str, output_path: str) -> bool:
        """Fallback to Coqui TTS (local, free)."""
        try:
            from TTS.api import TTS
            tts = TTS("tts_models/en/vctk/vits")
            tts.tts_to_file(text=text, file_path=output_path)
            return True
        except Exception as e:
            print(f"Coqui TTS error: {e}")
            return False

    # ============ MEMORY EXTRACTION ============
    async def extract_memories(self, user_text: str, ai_response: str) -> List[Dict[str, str]]:
        """Extract key facts worth remembering from exchange."""
        try:
            extraction_prompt = f"""From this conversation exchange, extract 0-2 key facts about the user worth remembering long-term.
            Be selective — only important preferences, experiences, or feelings.

            User: {user_text}
            Assistant: {ai_response}

            Return JSON array: [{{"category": "preference|fact|emotion|event", "content": "...", "importance": 0.8}}]
            Return [] if nothing significant."""

            response = await openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.3,
                max_tokens=200
            )

            import json
            content = response.choices[0].message.content
            # Extract JSON from possible markdown
            if "```" in content:
                content = content.split("```")[1].replace("json", "")

            memories = json.loads(content.strip())
            return memories if isinstance(memories, list) else []
        except Exception as e:
            print(f"Memory extraction error: {e}")
            return []

    def clear_session(self, session_id: str):
        """Clear conversation cache for session."""
        self.conversation_cache.pop(session_id, None)

# Global engine instance
ai_engine = AIEngine(persona="aurora")
