"""Redis connection utility for caching, rate limiting, and session tracking."""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client():
    """Return a singleton Redis client instance, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = settings.redis_url or settings.upstash_redis_url
    if not url:
        return None

    try:
        import redis
        client = redis.from_url(url, decode_responses=True)
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("Could not initialize Redis client: %s", exc)
        return None

