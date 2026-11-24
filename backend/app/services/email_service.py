"""Brevo Transactional Email Service for WavyGo Vendor Platform."""

import logging
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    to_name: Optional[str] = None,
) -> bool:
    """Send a transactional email using Brevo REST API."""
    api_key = settings.brevo_api_key
    if not api_key:
        logger.warning("Brevo API key is not configured. Email to %s skipped.", to_email)
        return False

    sender_email = settings.brevo_sender_email or "garv@wavygo.in"
    sender_name = settings.brevo_sender_name or "WavyGo"

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email.strip(),
        },
        "to": [
            {
                "email": to_email.strip(),
                "name": to_name or to_email.strip(),
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key.strip(),
        "content-type": "application/json",
    }

    if httpx is not None:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(BREVO_API_URL, json=payload, headers=headers)
                if response.status_code in (200, 201, 202):
                    logger.info("Email '%s' sent successfully to %s", subject, to_email)
                    return True
                else:
                    logger.error(
                        "Brevo send email failed (%s): %s", response.status_code, response.text
                    )
                    return False
        except Exception as exc:
            logger.exception("Failed to send email to %s via Brevo: %s", to_email, exc)
            return False
    else:
        import json
        import urllib.request
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(BREVO_API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                status_code = resp.getcode()
                if 200 <= status_code < 300:
                    logger.info("Email '%s' sent successfully to %s (urllib fallback)", subject, to_email)
                    return True
                return False
        except Exception as exc:
            logger.exception("Failed to send email to %s via Brevo (urllib fallback): %s", to_email, exc)
            return False


def send_signup_otp_email(to_email: str, otp: str, name: Optional[str] = None) -> bool:
    """Send email with 6-digit OTP for vendor signup verification."""
    subject = f"{otp} is your WavyGo verification code"
    recipient_name = name or "Partner"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WavyGo Email Verification</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #0B1020;
      color: #E2E8F0;
      margin: 0;
      padding: 30px 15px;
    }}
    .container {{
      max-width: 540px;
      margin: 0 auto;
      background: #111827;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }}
    .header {{
      background: linear-gradient(135deg, #064E3B 0%, #065F46 50%, #047857 100%);
      padding: 32px 30px;
      text-align: center;
    }}
    .logo {{
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.04em;
      color: #FFFFFF;
      margin: 0;
    }}
    .logo span {{
      color: #9BE7C4;
    }}
    .header-sub {{
      color: rgba(255, 255, 255, 0.85);
      font-size: 13px;
      margin-top: 6px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      font-weight: 600;
    }}
    .content {{
      padding: 36px 30px;
      background-color: #111827;
    }}
    .greeting {{
      font-size: 18px;
      font-weight: 600;
      color: #FFFFFF;
      margin-top: 0;
      margin-bottom: 12px;
    }}
    .message {{
      font-size: 14px;
      line-height: 1.6;
      color: #94A3B8;
      margin-bottom: 28px;
    }}
    .otp-box {{
      background: rgba(16, 185, 129, 0.08);
      border: 1.5px dashed #10B981;
      border-radius: 12px;
      padding: 24px 16px;
      text-align: center;
      margin-bottom: 28px;
    }}
    .otp-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #6EE7B7;
      font-weight: 600;
      margin-bottom: 8px;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 38px;
      font-weight: 800;
      letter-spacing: 8px;
      color: #34D399;
      margin: 0;
    }}
    .expiry {{
      font-size: 12px;
      color: #64748B;
      text-align: center;
      margin-top: 8px;
    }}
    .security-notice {{
      background: #1E293B;
      border-left: 3px solid #F59E0B;
      padding: 14px 16px;
      border-radius: 6px;
      font-size: 12px;
      color: #CBD5E1;
      line-height: 1.5;
      margin-bottom: 24px;
    }}
    .footer {{
      padding: 20px 30px;
      background-color: #0F172A;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      text-align: center;
      font-size: 11px;
      color: #64748B;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1 class="logo">Wavy<span>Go</span></h1>
      <div class="header-sub">Vendor Fleet Portal</div>
    </div>
    <div class="content">
      <h2 class="greeting">Hello {recipient_name},</h2>
      <p class="message">
        Thank you for choosing WavyGo to manage your vehicle rental fleet.
        Please use the 6-digit verification code below to complete your partner account registration:
      </p>

      <div class="otp-box">
        <div class="otp-label">Verification Code</div>
        <div class="otp-code">{otp}</div>
        <div class="expiry">Valid for 10 minutes</div>
      </div>

      <div class="security-notice">
        <strong>Security Notice:</strong> Never share this code with anyone. WavyGo staff will never ask for your verification code. If you did not attempt to sign up, please disregard this email.
      </div>
    </div>
    <div class="footer">
      &copy; 2026 WavyGo Technologies Pvt. Ltd. All rights reserved.<br>
      This is an automated system email sent via Brevo. Please do not reply directly.
    </div>
  </div>
</body>
</html>"""

    return send_email(to_email=to_email, subject=subject, html_content=html_content, to_name=name)


def send_welcome_email(to_email: str, business_name: str) -> bool:
    """Send welcome onboarding email to newly registered vendor."""
    subject = f"Welcome to WavyGo, {business_name}!"
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Welcome to WavyGo</title>
</head>
<body style="font-family: sans-serif; background-color: #0B1020; color: #E2E8F0; padding: 30px;">
  <div style="max-width: 500px; margin: 0 auto; background: #111827; border-radius: 12px; padding: 24px; border: 1px solid #1E293B;">
    <h2 style="color: #34D399; margin-top: 0;">Welcome to WavyGo! 🎉</h2>
    <p>Hi <strong>{business_name}</strong>,</p>
    <p>Your partner account is active and verified. You can now:</p>
    <ul>
      <li>Add and manage your fleet vehicles</li>
      <li>Record in-store & online bookings</li>
      <li>Track payments, deposits, and fuel/maintenance expenses</li>
      <li>Manage staff permissions & view live business reports</li>
    </ul>
    <p>We're thrilled to have you on board!</p>
    <p style="color: #94A3B8; font-size: 12px; margin-top: 30px;">— The WavyGo Partner Team</p>
  </div>
</body>
</html>"""
    return send_email(to_email=to_email, subject=subject, html_content=html_content, to_name=business_name)

