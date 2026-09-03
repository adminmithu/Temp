import requests
import logging
import html
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def clean_html(text: str) -> str:
    """Safely escape HTML special characters to prevent Telegram API entity parse errors."""
    if not text:
        return ""
    return html.escape(str(text))

def send_telegram_sms_alert(sms: dict) -> bool:
    """
    Format and send an SMS notification to the configured Telegram Group / Channel.
    - Uses 1-click copy code block <code>...</code> for OTP and Phone Number.
    - Uses Telegram Blockquote <blockquote>...</blockquote> for Full Message.
    - Escapes HTML entities to prevent 400 parse errors.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        logging.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_GROUP_ID is missing!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    otp = sms.get("otp_code", "N/A")
    clean_otp = clean_html(otp)
    otp_formatted = f"<code>{clean_otp}</code>" if (clean_otp and clean_otp != "N/A") else "N/A"

    clean_country = clean_html(sms.get('country', 'Unknown'))
    clean_number = clean_html(sms.get('phone_number', ''))
    clean_service = clean_html(sms.get('service', 'SMS Verification'))
    clean_msg = clean_html(sms.get('full_text', ''))
    clean_time = clean_html(sms.get('time', 'Just now'))
    flag = sms.get('flag', '🌐')

    message_html = (
        f"📩 <b>NEW SMS RECEIVED!</b>\n"
        f"🏳️ <b>Country:</b> {flag} {clean_country}\n"
        f"📱 <b>Phone Number:</b> <code>{clean_number}</code>\n"
        f"👤 <b>Sender / Service:</b> <b>{clean_service}</b>\n"
        f"🔑 <b>OTP Code:</b> {otp_formatted} <i>(Tap to copy)</i>\n\n"
        f"💬 <b>Full Message:</b>\n"
        f"<blockquote>{clean_msg}</blockquote>\n\n"
        f"⏰ <b>Time:</b> {clean_time}"
    )

    payload = {
        "chat_id": str(TELEGRAM_GROUP_ID),
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()

        if res_data.get("ok"):
            logging.info(f"✅ Forwarded SMS for {clean_number} [{clean_service}] to group {TELEGRAM_GROUP_ID}.")
            return True
        else:
            logging.error(f"❌ Telegram API Error: {res_data.get('description')}")
            return False
    except Exception as e:
        logging.error(f"❌ Failed to send Telegram message: {e}")
        return False

def send_private_user_sms_alert(user_id: int, sms: dict) -> bool:
    """Send private SMS alert directly to a user when their selected number receives an SMS."""
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    otp = sms.get("otp_code", "N/A")
    clean_otp = clean_html(otp)
    otp_formatted = f"<code>{clean_otp}</code>" if (clean_otp and clean_otp != "N/A") else "N/A"

    clean_country = clean_html(sms.get('country', 'Unknown'))
    clean_number = clean_html(sms.get('phone_number', ''))
    clean_service = clean_html(sms.get('service', 'SMS Verification'))
    clean_msg = clean_html(sms.get('full_text', ''))
    clean_time = clean_html(sms.get('time', 'Just now'))
    flag = sms.get('flag', '🌐')

    message_html = (
        f"🎉 <b>YOUR SMS HAS ARRIVED!</b>\n\n"
        f"🏳️ <b>Country:</b> {flag} {clean_country}\n"
        f"📱 <b>Your Number:</b> <code>{clean_number}</code>\n"
        f"👤 <b>Service:</b> <b>{clean_service}</b>\n"
        f"🔑 <b>OTP Code:</b> {otp_formatted} <i>(Tap to copy)</i>\n\n"
        f"💬 <b>Full Message:</b>\n"
        f"<blockquote>{clean_msg}</blockquote>\n\n"
        f"⏰ <b>Time:</b> {clean_time}"
    )

    payload = {
        "chat_id": user_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        logging.error(f"Failed to send private user SMS alert: {e}")
        return False

def send_group_notice(notice_text: str) -> bool:
    """Send an official announcement or new number notification to the Telegram group."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": str(TELEGRAM_GROUP_ID),
        "text": notice_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        logging.error(f"Failed to post group notice: {e}")
        return False
