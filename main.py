import time
import logging
import sys
import io
import os
import threading
import asyncio
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from config import SCAN_INTERVAL, TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_ID, ADMIN_ID
from database import (
    init_db, generate_sms_hash, is_sms_seen, mark_sms_seen,
    is_country_enabled, is_number_enabled, add_stocked_number,
    get_subscriptions_for_number
)
from scraper import TempPhoneScraper
from telegram_notifier import send_telegram_sms_alert, send_private_user_sms_alert
from admin_bot import create_admin_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Global target numbers cache
target_numbers_cache = []
last_cache_time = 0

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP Health Check Handler for Render Free Web Service tier."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Running Live 24/7!")

    def log_message(self, format, *args):
        return # Silent HTTP logs

def start_health_check_server():
    """Start lightweight HTTP server on $PORT for Render Free Web Service."""
    port = int(os.getenv("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logging.info(f"🌐 Health Check HTTP Server running on port {port} for Render Free Web Service.")
        server.serve_forever()
    except Exception as e:
        logging.error(f"HTTP Server error: {e}")

def start_admin_bot_thread():
    """Run Telegram Admin Bot in a background thread with auto-retry on network disconnects."""
    while True:
        try:
            app = create_admin_app()
            if app:
                logging.info("🤖 Starting Telegram Admin Bot Polling...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                app.run_polling(stop_signals=None, close_loop=False)
        except Exception as e:
            logging.error(f"Admin Bot loop error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def process_number_sms(scraper: TempPhoneScraper, num_dict: dict) -> int:
    """Scan a single number for new SMS, post alerts to Group, and notify subscribed users privately."""
    num = num_dict["number"]
    country_name = num_dict["country"]

    if not is_country_enabled(country_name) or not is_number_enabled(num):
        return 0

    add_stocked_number(num, country_name, num_dict["url"])

    new_sms_count = 0
    sms_list = scraper.fetch_latest_sms(num_dict, country_name)

    for sms in sms_list:
        sms_hash = generate_sms_hash(
            sms["phone_number"],
            sms["full_text"],
            sms.get("time", "")
        )

        if not is_sms_seen(sms_hash):
            new_sms_count += 1

            print("\n" + "-" * 50)
            print(f"⚡ INSTANT FRESH SMS DETECTED!")
            print(f"Country: {sms['flag']} {sms['country']}")
            print(f"Number:  {sms['phone_number']}")
            print(f"Service: {sms['service']}")
            print(f"OTP:     {sms['otp_code']}")
            print(f"Message: {sms['full_text']}")
            print("-" * 50)

            # 1. ALWAYS send to Telegram Group
            send_telegram_sms_alert(sms)

            # 2. ALSO send Private Alert to user if subscribed
            subs = get_subscriptions_for_number(sms["phone_number"])
            for sub in subs:
                target_user_id = sub["user_id"]
                sub_service = sub["service_name"]
                if sub_service == "ALL" or sub_service.lower() in sms["service"].lower() or sms["service"].lower() in sub_service.lower():
                    send_private_user_sms_alert(target_user_id, sms)

            # Mark as seen in SQLite database
            mark_sms_seen(
                sms_hash,
                sms["phone_number"],
                sms["country"],
                sms["service"],
                sms["otp_code"]
            )

            time.sleep(0.3)

    return new_sms_count

def run_scanner_loop():
    """Anti-429 Protected Instant Parallel Scanner Loop."""
    global target_numbers_cache, last_cache_time

    print("=" * 60)
    print("🚀 INSTANT FRESH SMS AUTO-FORWARDER BOT STARTED")
    print("=" * 60)

    init_db()
    scraper = TempPhoneScraper()

    loop_count = 0

    while True:
        loop_count += 1
        now = time.time()

        # Refresh target numbers list every 2 minutes (120s)
        if not target_numbers_cache or (now - last_cache_time) > 120:
            logging.info("🌐 Refreshing active phone numbers list across pages...")
            target_numbers_cache = scraper.fetch_all_active_numbers(max_pages=5)
            last_cache_time = now
            logging.info(f"⚡ Scheduled {len(target_numbers_cache)} active phone numbers for live scanning.")

        logging.info(f"--- Starting Instant Scan Loop #{loop_count} ({len(target_numbers_cache)} Numbers) ---")

        try:
            total_new_sms = 0
            # 12 Workers to maintain high speed without Cloudflare rate limits
            with ThreadPoolExecutor(max_workers=12) as executor:
                futures = [
                    executor.submit(process_number_sms, scraper, num_dict)
                    for num_dict in target_numbers_cache
                ]
                for future in as_completed(futures):
                    try:
                        total_new_sms += future.result()
                    except Exception as ex:
                        pass

            logging.info(f"Scan Loop #{loop_count} Complete. Fresh Instant SMS Forwarded: {total_new_sms}")

        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user.")
            sys.exit(0)
        except Exception as e:
            logging.error(f"Error in scan loop: {e}")

        time.sleep(3)

if __name__ == "__main__":
    # Start HTTP Health Server thread for Render Free Web Service
    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()

    # Start Telegram Admin Bot thread
    admin_thread = threading.Thread(target=start_admin_bot_thread, daemon=True)
    admin_thread.start()

    # Start Scanner Loop
    run_scanner_loop()
