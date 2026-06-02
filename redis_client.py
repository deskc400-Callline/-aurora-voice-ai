"""Redis client for session state and real-time data."""
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any, List
from config import settings

class RedisManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection."""
        kwargs = {"decode_responses": True}
        if settings.REDIS_PASSWORD:
            kwargs["password"] = settings.REDIS_PASSWORD

        self.redis = redis.from_url(settings.REDIS_URL, **kwargs)

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    # Session Management
    async def create_session(self, session_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """Store active WebRTC session."""
        key = f"session:{session_id}"
        data.update({
            "user_id": user_id,
            "created_at": str(datetime.utcnow()),
            "status": "waiting"  # waiting, connecting, active, ended
        })
        await self.redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()})
        await self.redis.expire(key, settings.SESSION_TIMEOUT)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        key = f"session:{session_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        return {k: json.loads(v) if v.startswith("{") or v.startswith("[") else v for k, v in data.items()}

    async def update_session_status(self, session_id: str, status: str) -> None:
        """Update session status."""
        key = f"session:{session_id}"
        await self.redis.hset(key, "status", status)

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(f"session:{session_id}")

    # ICE Candidate Queue (for buffering before peer connection is ready)
    async def queue_ice_candidate(self, session_id: str, candidate: Dict[str, Any], sender: str) -> None:
        """Queue ICE candidate for later delivery."""
        key = f"ice_queue:{session_id}:{sender}"
        await self.redis.lpush(key, json.dumps(candidate))
        await self.redis.expire(key, 300)  # 5 min timeout

    async def get_ice_queue(self, session_id: str, sender: str) -> List[Dict[str, Any]]:
        """Get and clear ICE candidate queue."""
        key = f"ice_queue:{session_id}:{sender}"
        candidates = await self.redis.lrange(key, 0, -1)
        await self.redis.delete(key)
        return [json.loads(c) for c in candidates]

    # Conversation Cache (for quick access during call)
    async def cache_conversation(self, session_id: str, messages: List[Dict[str, str]]) -> None:
        """Cache conversation history in Redis."""
        key = f"conversation:{session_id}"
        # Store as JSON list
        await self.redis.set(key, json.dumps(messages[-20:]), ex=settings.SESSION_TIMEOUT)

    async def get_cached_conversation(self, session_id: str) -> List[Dict[str, str]]:
        """Get cached conversation."""
        key = f"conversation:{session_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else []

    async def append_to_conversation(self, session_id: str, message: Dict[str, str]) -> None:
        """Append message to cached conversation."""
        messages = await self.get_cached_conversation(session_id)
        messages.append(message)
        # Keep only last 20 messages
        messages = messages[-20:]
        await self.cache_conversation(session_id, messages)

    # Online Status
    async def set_user_online(self, user_id: str, socket_id: str) -> None:
        await self.redis.set(f"online:{user_id}", socket_id, ex=3600)

    async def get_user_socket(self, user_id: str) -> Optional[str]:
        return await self.redis.get(f"online:{user_id}")

    async def set_user_offline(self, user_id: str) -> None:
        await self.redis.delete(f"online:{user_id}")

    # Presence in rooms
    async def join_room(self, room_id: str, user_id: str, socket_id: str) -> None:
        await self.redis.sadd(f"room:{room_id}", f"{user_id}:{socket_id}")

    async def leave_room(self, room_id: str, user_id: str, socket_id: str) -> None:
        await self.redis.srem(f"room:{room_id}", f"{user_id}:{socket_id}")

    async def get_room_members(self, room_id: str) -> List[str]:
        members = await self.redis.smembers(f"room:{room_id}")
        return [m.split(":")[0] for m in members]

    # Rate Limiting
    async def check_rate_limit(self, user_id: str, action: str, max_requests: int = 10, window: int = 60) -> bool:
        key = f"rate_limit:{user_id}:{action}"
        current = await self.redis.get(key)
        if not current:
            await self.redis.setex(key, window, 1)
            return True
        if int(current) >= max_requests:
            return False
        await self.redis.incr(key)
        return True

# Global instance
redis_manager = RedisManager()

from datetime import datetime
