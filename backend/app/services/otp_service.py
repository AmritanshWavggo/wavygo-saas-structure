"""OTP Generation, Storage & Verification Service using Upstash Redis."""

import logging
import secrets
import time
from typing import Dict, Tuple

from app.db.redis import get_redis_client

logger = logging.getLogger(__name__)

# Fallback store for test suites or offline local development
_in_memory_otps: Dict[str, Tuple[str, float]] = {}
_last_otp_request_time: Dict[str, float] = {}


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure random numeric OTP."""
    # 6-digit numeric OTP between 100000 and 999999
    lower_bound = 10 ** (length - 1)
    upper_bound = (10 ** length) - 1
    code = secrets.randbelow(upper_bound - lower_bound + 1) + lower_bound
    return str(code)


def check_otp_rate_limit(email: str, cooldown_seconds: int = 30) -> Tuple[bool, int]:
    """
    Check if the user has requested an OTP recently.
    Returns (can_send, seconds_to_wait).
    """
    norm_email = email.lower().strip()
    redis = get_redis_client()
    now = time.time()

    if redis is not None:
        try:
            cooldown_key = f"otp:cooldown:{norm_email}"
            raw_ttl = redis.ttl(cooldown_key)
            ttl = int(raw_ttl) if isinstance(raw_ttl, (int, float)) else 0
            if ttl > 0:
                return False, ttl
            # Set cooldown
            redis.setex(cooldown_key, cooldown_seconds, "1")
            return True, 0
        except Exception as exc:
            logger.warning("Redis cooldown check failed: %s, using fallback", exc)

    # In-memory cooldown fallback
    last_time = _last_otp_request_time.get(norm_email, 0)
    elapsed = now - last_time
    if elapsed < cooldown_seconds:
        return False, int(cooldown_seconds - elapsed)

    _last_otp_request_time[norm_email] = now
    return True, 0


def store_signup_otp(email: str, otp: str, ttl_seconds: int = 600) -> bool:
    """
    Store the OTP in Upstash Redis with a TTL (default 10 minutes).
    Falls back to in-memory dictionary if Redis is unreachable.
    """
    norm_email = email.lower().strip()
    redis_key = f"otp:signup:{norm_email}"
    redis = get_redis_client()

    stored_in_redis = False
    if redis is not None:
        try:
            redis.setex(redis_key, ttl_seconds, otp)
            stored_in_redis = True
            logger.info("Stored OTP in Upstash Redis for %s (TTL: %ds)", norm_email, ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to store OTP in Redis: %s", exc)

    # Always keep in in-memory fallback store as well for safety & test suites
    _in_memory_otps[norm_email] = (otp, time.time() + ttl_seconds)
    return True


def verify_signup_otp(email: str, otp: str) -> bool:
    """
    Verify the submitted OTP against Upstash Redis or fallback store.
    If valid, the OTP is consumed (deleted) to prevent replay.
    """
    norm_email = email.lower().strip()
    redis_key = f"otp:signup:{norm_email}"
    redis = get_redis_client()
    provided_code = str(otp).strip()

    # 1. Check Redis
    if redis is not None:
        try:
            stored_code = redis.get(redis_key)
            if stored_code:
                # Upstash may return string or bytes
                if isinstance(stored_code, bytes):
                    stored_code = stored_code.decode("utf-8")
                if secrets.compare_digest(str(stored_code).strip(), provided_code):
                    redis.delete(redis_key)
                    _in_memory_otps.pop(norm_email, None)
                    logger.info("OTP verified successfully via Upstash Redis for %s", norm_email)
                    return True
        except Exception as exc:
            logger.warning("Redis OTP verification error: %s", exc)

    # 2. Check fallback store
    fallback = _in_memory_otps.get(norm_email)
    if fallback is not None:
        saved_code, expires_at = fallback
        if time.time() <= expires_at and secrets.compare_digest(saved_code, provided_code):
            _in_memory_otps.pop(norm_email, None)
            if redis is not None:
                try:
                    redis.delete(redis_key)
                except Exception:
                    pass
            logger.info("OTP verified successfully via fallback store for %s", norm_email)
            return True

    logger.warning("Invalid or expired OTP attempt for %s", norm_email)
    return False


def _normalize_target(target: str, channel: str) -> str:
    if channel.lower() == "email":
        return target.lower().strip()
    import re
    digits = re.sub(r"\D", "", target)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits


def store_customer_otp(target: str, channel: str, otp: str, ttl_seconds: int = 600) -> bool:
    """Store OTP in Upstash Redis for customer email or phone verification."""
    norm = _normalize_target(target, channel)
    redis_key = f"otp:cust:{channel.lower()}:{norm}"
    redis = get_redis_client()

    if redis is not None:
        try:
            redis.setex(redis_key, ttl_seconds, otp)
            logger.info("Stored customer %s OTP in Upstash Redis for %s (TTL: %ds)", channel, norm, ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to store customer OTP in Redis: %s", exc)

    _in_memory_otps[f"{channel.lower()}:{norm}"] = (otp, time.time() + ttl_seconds)
    return True


def verify_customer_otp(target: str, channel: str, otp: str) -> bool:
    """Verify customer OTP against Upstash Redis or fallback store."""
    norm = _normalize_target(target, channel)
    redis_key = f"otp:cust:{channel.lower()}:{norm}"
    redis = get_redis_client()
    provided = str(otp).strip()

    # 1. Redis
    if redis is not None:
        try:
            stored = redis.get(redis_key)
            if stored:
                if isinstance(stored, bytes):
                    stored = stored.decode("utf-8")
                if secrets.compare_digest(str(stored).strip(), provided):
                    redis.delete(redis_key)
                    _in_memory_otps.pop(f"{channel.lower()}:{norm}", None)
                    logger.info("Customer %s OTP verified successfully for %s", channel, norm)
                    return True
        except Exception as exc:
            logger.warning("Redis customer OTP verification error: %s", exc)

    # 2. Fallback
    fallback_key = f"{channel.lower()}:{norm}"
    fallback = _in_memory_otps.get(fallback_key)
    if fallback is not None:
        saved_code, expires_at = fallback
        if time.time() <= expires_at and secrets.compare_digest(saved_code, provided):
            _in_memory_otps.pop(fallback_key, None)
            if redis is not None:
                try:
                    redis.delete(redis_key)
                except Exception:
                    pass
            logger.info("Customer %s OTP verified via fallback for %s", channel, norm)
            return True

    return False


def store_booking_otp(
    phone_or_id: str, purpose: str, otp: str, ttl_seconds: int = 600
) -> bool:
    """Store booking OTP (pickup or return) in Upstash Redis."""
    import re
    digits = re.sub(r"\D", "", phone_or_id)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    clean = digits if len(digits) >= 10 else phone_or_id.strip().lower()
    redis_key = f"otp:booking:{purpose.lower()}:{clean}"
    redis = get_redis_client()

    if redis is not None:
        try:
            redis.setex(redis_key, ttl_seconds, otp)
            logger.info("Stored booking %s OTP in Upstash Redis for %s (TTL: %ds)", purpose, clean, ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to store booking OTP in Redis: %s", exc)

    _in_memory_otps[f"booking:{purpose.lower()}:{clean}"] = (otp, time.time() + ttl_seconds)
    return True


def verify_booking_otp(
    phone_or_id: str, purpose: str, otp: str
) -> bool:
    """Verify booking OTP (pickup or return) against Upstash Redis."""
    import re
    digits = re.sub(r"\D", "", phone_or_id)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    clean = digits if len(digits) >= 10 else phone_or_id.strip().lower()
    redis_key = f"otp:booking:{purpose.lower()}:{clean}"
    redis = get_redis_client()
    provided = str(otp).strip()

    # 1. Redis
    if redis is not None:
        try:
            stored = redis.get(redis_key)
            if stored:
                if isinstance(stored, bytes):
                    stored = stored.decode("utf-8")
                if secrets.compare_digest(str(stored).strip(), provided):
                    redis.delete(redis_key)
                    _in_memory_otps.pop(f"booking:{purpose.lower()}:{clean}", None)
                    logger.info("Booking %s OTP verified successfully for %s", purpose, clean)
                    return True
        except Exception as exc:
            logger.warning("Redis booking OTP verification error: %s", exc)

    # 2. Fallback
    fallback_key = f"booking:{purpose.lower()}:{clean}"
    fallback = _in_memory_otps.get(fallback_key)
    if fallback is not None:
        saved_code, expires_at = fallback
        if time.time() <= expires_at and secrets.compare_digest(saved_code, provided):
            _in_memory_otps.pop(fallback_key, None)
            if redis is not None:
                try:
                    redis.delete(redis_key)
                except Exception:
                    pass
            logger.info("Booking %s OTP verified via fallback for %s", purpose, clean)
            return True

    return False


