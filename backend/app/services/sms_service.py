"""SMS Notification & OTP Service using Edumarc SMS."""

import logging
import re
from typing import Any, Dict, Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_mobile(phone: str) -> str:
    """Extract clean 10-digit mobile number or 12-digit with 91 prefix."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) > 10 and digits.startswith("0"):
        return digits[1:]
    return digits


def send_sms_otp(
    phone: str,
    otp: str,
    customer_name: Optional[str] = None,
) -> bool:
    """
    Send an OTP via Edumarc SMS API using the registered DLT template.

    Template:
    "Dear Nowmadx user, your OTP for login is: {otp}. This code is valid for 2 minutes. OTP is confidential. Do not share it with anyone. - EDUMARC"
    """
    api_key = settings.sms_api_key
    if not api_key:
        logger.warning("SMS_API_KEY is not configured. SMS to %s skipped.", phone)
        return False

    clean_phone = normalize_mobile(phone)
    if not clean_phone or len(clean_phone) < 10:
        logger.warning("Invalid phone number format for SMS: %s", phone)
        return False

    url = settings.sms_api_url or "https://smsapi.edumarcsms.com/api/v1/sendsms"
    sender_id = settings.sms_sender_id or "EDUMRC"
    template_id = settings.sms_template_id or "1707178064151587006"

    # DLT approved template text
    message = (
        f"Dear Nowmadx user, your OTP for login is: {otp}. "
        f"This code is valid for 2 minutes. OTP is confidential. "
        f"Do not share it with anyone. - EDUMARC"
    )

    payload: Dict[str, Any] = {
        "number": [clean_phone],
        "message": message,
        "sender_id": sender_id,
        "template_id": template_id,
    }

    headers = {
        "apikey": api_key.strip(),
        "Content-Type": "application/json",
    }

    try:
        if httpx is None:
            logger.error("httpx package is missing; cannot send SMS.")
            return False

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    logger.info("SMS OTP successfully sent to %s (Tx: %s)", clean_phone, data.get("data", {}).get("transactionId"))
                    return True
                logger.warning("Edumarc SMS API returned unsuccessful: %s", data)
                return False
            logger.warning("Edumarc SMS API returned HTTP %s: %s", resp.status_code, resp.text)
            return False
    except Exception as exc:
        logger.error("Failed to send SMS OTP to %s: %s", clean_phone, exc)
        return False
