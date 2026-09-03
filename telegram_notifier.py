import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def send_telegram_sms_alert(sms: dict) -> bool:
    """
    Format and send an SMS notification to the configured Telegram Group / Channel.
    - Uses 1-click copy code block <code>...</code> for OTP and Phone Number.
    - Uses Telegram Blockquote <blockquote>...</blockquote> for Full Message.
    - Excludes website source link per user request.
    """
    if not TELEGRAM_BOT_TOKEN:
        logging.warning("TELEGRAM_BOT_TOKEN is not set in .env!")
        return False
        
    if not TELEGRAM_GROUP_ID:
        logging.warning("TELEGRAM_GROUP_ID is not set in .env!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    otp = sms.get("otp_code", "N/A")
    otp_formatted = f"<code>{otp}</code>" if (otp and otp != "N/A") else "N/A"

    message_html = (
        f"📩 <b>NEW SMS RECEIVED!</b>\n"
        f"🏳️ <b>Country:</b> {sms['flag']} {sms['country']}\n"
        f"📱 <b>Phone Number:</b> <code>{sms['phone_number']}</code>\n"
        f"👤 <b>Sender / Service:</b> <b>{sms['service']}</b>\n"
        f"🔑 <b>OTP Code:</b> {otp_formatted} <i>(Tap to copy)</i>\n\n"
        f"💬 <b>Full Message:</b>\n"
        f"<blockquote>{sms['full_text']}</blockquote>\n\n"
        f"⏰ <b>Time:</b> {sms.get('time', 'Just now')}"
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
            logging.info(f"✅ Forwarded SMS for {sms['phone_number']} [{sms['service']}] to group {TELEGRAM_GROUP_ID}.")
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
    otp_formatted = f"<code>{otp}</code>" if (otp and otp != "N/A") else "N/A"

    message_html = (
        f"🎉 <b>YOUR SMS HAS ARRIVED!</b>\n\n"
        f"🏳️ <b>Country:</b> {sms['flag']} {sms['country']}\n"
        f"📱 <b>Your Number:</b> <code>{sms['phone_number']}</code>\n"
        f"👤 <b>Service:</b> <b>{sms['service']}</b>\n"
        f"🔑 <b>OTP Code:</b> {otp_formatted} <i>(Tap to copy)</i>\n\n"
        f"💬 <b>Full Message:</b>\n"
        f"<blockquote>{sms['full_text']}</blockquote>\n\n"
        f"⏰ <b>Time:</b> {sms.get('time', 'Just now')}"
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
