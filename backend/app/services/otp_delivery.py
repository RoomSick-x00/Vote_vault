"""One-time-code delivery. Providers never return codes to callers."""
import re
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.errors import ApiError


def deliver_otp(settings, channel: str, contact: str, code: str) -> tuple[str | None, str | None]:
    provider = (settings.otp_email_provider if channel == "email" else settings.otp_phone_provider).lower().strip()
    if provider == "development":
        if settings.app_env.lower() not in ("development", "test"):
            raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "Development OTP delivery is disabled in this environment.")
        return code, None
    message = f"Your VoteVault verification code is {code}. It expires in 10 minutes."
    if channel == "email" and provider == "smtp":
        if not settings.smtp_host or not settings.smtp_from or settings.smtp_security not in ("ssl", "starttls"):
            raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "Email delivery is not configured.")
        if bool(settings.smtp_username) != bool(settings.smtp_password):
            raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "Email delivery credentials are incomplete.")
        mail = EmailMessage()
        mail["From"] = settings.smtp_from
        mail["To"] = contact
        mail["Subject"] = "Your VoteVault verification code"
        mail.set_content(message)
        try:
            context = ssl.create_default_context()
            if settings.smtp_security == "ssl":
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            with server:
                if settings.smtp_security == "starttls":
                    server.starttls(context=context)
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(mail)
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            raise ApiError(502, "OTP_DELIVERY_FAILED", "The email provider could not accept the code. Please try again.") from exc
        return None, None
    if channel == "phone" and provider == "twilio_verify":
        if not all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_verify_service_sid)):
            raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "Twilio Verify is not configured.")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", contact):
            raise ApiError(422, "INVALID_PHONE", "Use an international phone number such as +919876543210.")
        try:
            response = httpx.post(
                f"https://verify.twilio.com/v2/Services/{settings.twilio_verify_service_sid}/Verifications",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={"To": contact, "Channel": "sms"}, timeout=10,
            )
            response.raise_for_status()
            sid = response.json().get("sid", "")
            if not re.fullmatch(r"VE[0-9a-fA-F]{32}", sid):
                raise ValueError("Invalid verification reference")
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(502, "OTP_DELIVERY_FAILED", "The SMS provider could not accept the code. Check the trial account and recipient, then try again.") from exc
        return None, "tv:" + sid
    if channel == "phone" and provider == "twilio":
        if not all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number)):
            raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "SMS delivery is not configured.")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", contact):
            raise ApiError(422, "INVALID_PHONE", "Use an international phone number such as +919876543210.")
        try:
            response = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={"To": contact, "From": settings.twilio_from_number, "Body": message},
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ApiError(502, "OTP_DELIVERY_FAILED", "The SMS provider could not accept the code. Please try again.") from exc
        return None, None
    raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", f"OTP delivery is not configured for {channel}.")


def check_twilio_verify(settings, marker: str, code: str) -> bool:
    if not all((settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_verify_service_sid)):
        raise ApiError(503, "OTP_DELIVERY_NOT_CONFIGURED", "Twilio Verify is not configured.")
    try:
        response = httpx.post(
            f"https://verify.twilio.com/v2/Services/{settings.twilio_verify_service_sid}/VerificationCheck",
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={"VerificationSid": marker[3:], "Code": code}, timeout=10,
        )
        response.raise_for_status()
        return response.json().get("status") == "approved"
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(502, "OTP_VERIFICATION_UNAVAILABLE", "The SMS provider could not verify the code. Please try again.") from exc
