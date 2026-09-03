import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8977584755:AAH-KcUCgqKXexuYQfZa-BOO74atkDgtEcI")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID", "-1003922823297")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1262396547"))

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "10"))

LOGIN_EMAIL = os.getenv("LOGIN_EMAIL", "mithuchandra647@gmail.com")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "Mithu@808")

BASE_URL = "https://temporary-phone-number.com"
COUNTRIES_URL = "https://temporary-phone-number.com/countrys/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
