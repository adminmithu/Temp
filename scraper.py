from curl_cffi import requests as c_requests
from bs4 import BeautifulSoup
import re
import logging
import time
import random
import hashlib
from config import BASE_URL, COUNTRIES_URL, HEADERS, LOGIN_EMAIL, LOGIN_PASSWORD

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

COUNTRY_FLAGS = {
    "UK": "🇬🇧",
    "United Kingdom": "🇬🇧",
    "Canada": "🇨🇦",
    "US": "🇺🇸",
    "USA": "🇺🇸",
    "United States": "🇺🇸",
    "Netherlands": "🇳🇱",
    "Finland": "🇫🇮",
    "Belgium": "🇧🇪",
    "Slovenia": "🇸🇮",
    "Poland": "🇵🇱",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "Austria": "🇦🇹",
    "Sweden": "🇸🇪",
    "China": "🇨🇳",
    "Philippines": "🇵🇭",
    "Spain": "🇪🇸",
    "Russia": "🇷🇺",
}

SERVICES_MAP = [
    ("WhatsApp", r"\bwhats?app\b"),
    ("Telegram", r"\btelegram\b"),
    ("Google / Gmail", r"\bgoogle\b|\bgmail\b|\bg-\d+"),
    ("Facebook", r"\bfacebook\b|\bfb\b"),
    ("TikTok", r"\btiktok\b"),
    ("Instagram", r"\binstagram\b|\big\b"),
    ("OpenAI / ChatGPT", r"\bopenai\b|\bchatgpt\b"),
    ("Amazon", r"\bamazon\b"),
    ("Microsoft", r"\bmicrosoft\b|\bmsft\b|\botp-auth\b"),
    ("Apple", r"\bapple\b|\bappleid\b"),
    ("PayPal", r"\bpaypal\b"),
    ("Uber", r"\buber\b"),
    ("Steam", r"\bsteam\b"),
    ("Snapchat", r"\bsnapchat\b"),
    ("Twitter / X", r"\btwitter\b|\bx\.com\b"),
    ("Viber", r"\bviber\b"),
    ("IMO", r"\bimo\b"),
    ("Discord", r"\bdiscord\b"),
    ("Binance", r"\bbinance\b"),
    ("Netflix", r"\bnetflix\b"),
    ("Tinder", r"\btinder\b"),
    ("Badoo", r"\bbadoo\b"),
    ("LinkedIn", r"\blinkedin\b"),
    ("Line", r"\bline\b"),
    ("WeChat", r"\bwechat\b"),
    ("VK", r"\bvk\.com\b|\bvkontakte\b"),
    ("Signal", r"\bsignal\b"),
    ("Firebase", r"\bfirebase\b"),
    ("Roblox", r"\broblox\b"),
    ("Nike", r"\bnike\b"),
    ("Alibaba / AliExpress", r"\balibaba\b|\baliexpress\b|\btaobao\b"),
    ("Claude / Anthropic", r"\bclaude\b|\banthropic\b"),
    ("Yahoo", r"\byahoo\b"),
    ("ProtonMail", r"\bproton\b"),
    ("OK.ru", r"\bok\.ru\b|\bodnoklassniki\b"),
    ("Yandex", r"\byandex\b"),
    ("Wyndham", r"\bwyndham\b"),
    ("Uber Eats", r"\bubereats\b"),
]

def get_country_flag(country_name: str) -> str:
    for key, flag in COUNTRY_FLAGS.items():
        if key.lower() in country_name.lower():
            return flag
    return "🌐"

def is_recent_sms(time_text: str) -> bool:
    """Filter out old historical SMS messages. Only allow INSTANT/RECENT SMS."""
    txt = time_text.lower().strip()
    if not txt or "just now" in txt or "sec" in txt:
        return True

    if "min" in txt:
        match = re.search(r'(\d+)\s*min', txt)
        if match:
            mins = int(match.group(1))
            return mins <= 30
        return True

    if any(k in txt for k in ["hour", "day", "month", "year"]):
        return False

    return True

def detect_service_name(message_text: str) -> str:
    for display_name, pattern in SERVICES_MAP:
        if re.search(pattern, message_text, re.IGNORECASE):
            return display_name

    patterns = [
        r'\b(?:your|from|welcome to|login to|register for)\s+([A-Z][a-zA-Z0-9.\-_]{2,15})\b',
        r'\b([A-Z][a-zA-Z0-9.\-_]{2,15})\s+(?:code|verification|otp|pin|security)\b',
        r'from\s+([a-zA-Z0-9.\-_]{3,20})'
    ]
    for pat in patterns:
        match = re.search(pat, message_text, re.IGNORECASE)
        if match:
            found_name = match.group(1).strip()
            if found_name.lower() not in ["temporary", "phone", "number", "verification", "security", "account", "mobile", "code", "your"]:
                return found_name.title()

    return "SMS Verification"

def extract_otp_code(message_text: str) -> str:
    """Extract FULL UNMASKED numeric OTP code from message text. Never return ****."""
    # 1. Match numeric code patterns like 123456, 123-456, G-123456
    match = re.search(r'(?:code|otp|pin|is|verification\s*code|kod|passcode|secret)[\s:\-\=]+([A-Z0-9]{4,8})\b', message_text, re.IGNORECASE)
    if match:
        code = match.group(1).strip()
        if not (len(code) == 4 and code.startswith("202")) and "*" not in code:
            return code

    hyphen_match = re.search(r'\b(\d{3}[-\s]\d{3})\b', message_text)
    if hyphen_match:
        c = hyphen_match.group(1).replace(" ", "")
        if "*" not in c:
            return c

    # Search for pure 4-8 digit numbers
    digits = re.findall(r'\b(\d{4,8})\b', message_text)
    for d in digits:
        if d.startswith("202") and len(d) == 4:
            continue
        if d.startswith("358") or d.startswith("447") or d.startswith("186"):
            continue
        if "*" not in d:
            return d

    # Alphanumeric fallback if pure digits not found
    code_match = re.search(r'\b([A-Z0-9]{4,8})\b', message_text)
    if code_match:
        c = code_match.group(1)
        if not c.startswith("202") and not c.startswith("http") and "*" not in c:
            return c

    return "Check Message"

class TempPhoneScraper:
    def __init__(self):
        # Impersonate Chrome browser TLS fingerprinting to bypass Cloudflare 403
        self.session = c_requests.Session(impersonate="chrome120")
        self.session.headers.update(HEADERS)
        self.is_logged_in = False
        self.login_to_website()

    def login_to_website(self):
        """Perform MD5 hashed login to temporary-phone-number.com to unlock FULL UNMASKED SMS OTP codes."""
        try:
            self.session.get("https://temporary-phone-number.com/auth/login", timeout=10)
            
            hashed_pass = hashlib.md5(LOGIN_PASSWORD.encode('utf-8')).hexdigest()
            payload = {
                "mail": LOGIN_EMAIL,
                "password": hashed_pass
            }
            res = self.session.post(
                "https://temporary-phone-number.com/ajax/login",
                json=payload,
                headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"},
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()
                if data.get("status"):
                    self.is_logged_in = True
                    logging.info("🔑 ✅ Scraper successfully authenticated on temporary-phone-number.com via MD5! Unmasked OTPs unlocked.")
                else:
                    logging.warning(f"Website login notice: {data.get('Msg')}")
        except Exception as e:
            logging.error(f"Error authenticating scraper: {e}")

    def fetch_all_active_numbers(self, max_pages: int = 5):
        """
        Fetch ALL active numbers with DEDICATED DIRECT SCRAPING for UK and Canada numbers!
        Ensures UK & Canada numbers get 100% priority scanning.
        """
        all_numbers = []
        try:
            # 1. DEDICATED DIRECT SCRAPE FOR UK NUMBERS
            uk_url = "https://temporary-phone-number.com/UK-Phone-Number/"
            time.sleep(0.3)
            uk_res = self.session.get(uk_url, timeout=10)
            if uk_res.status_code == 200:
                soup_uk = BeautifulSoup(uk_res.text, "html.parser")
                for a_tag in soup_uk.find_all("a", href=True):
                    href = a_tag["href"]
                    match = re.search(r'/UK-Phone-Number/(\d{8,})', href, re.I)
                    if match:
                        raw_num = match.group(1)
                        formatted_num = f"+{raw_num}"
                        full_url = href if href.startswith("http") else BASE_URL + href
                        if not any(n["number"] == formatted_num for n in all_numbers):
                            all_numbers.append({
                                "country": "UK",
                                "flag": "🇬🇧",
                                "number": formatted_num,
                                "raw_number": raw_num,
                                "url": full_url
                            })

            # 2. DEDICATED DIRECT SCRAPE FOR CANADA NUMBERS
            ca_url = "https://temporary-phone-number.com/Canada-Phone-Number/"
            time.sleep(0.3)
            ca_res = self.session.get(ca_url, timeout=10)
            if ca_res.status_code == 200:
                soup_ca = BeautifulSoup(ca_res.text, "html.parser")
                for a_tag in soup_ca.find_all("a", href=True):
                    href = a_tag["href"]
                    match = re.search(r'/Canada-Phone-Number/(\d{8,})', href, re.I)
                    if match:
                        raw_num = match.group(1)
                        formatted_num = f"+{raw_num}"
                        full_url = href if href.startswith("http") else BASE_URL + href
                        if not any(n["number"] == formatted_num for n in all_numbers):
                            all_numbers.append({
                                "country": "Canada",
                                "flag": "🇨🇦",
                                "number": formatted_num,
                                "raw_number": raw_num,
                                "url": full_url
                            })

            # 3. SCRAPE HOMEPAGE PAGES 1-5 FOR ALL OTHER ACTIVE COUNTRIES (US, Sweden, Netherlands, Finland, etc.)
            for page in range(1, max_pages + 1):
                url = f"https://temporary-phone-number.com/?page={page}" if page > 1 else "https://temporary-phone-number.com/"
                time.sleep(random.uniform(0.3, 0.5))
                
                res = self.session.get(url, timeout=10)
                if res.status_code in [403, 429]:
                    time.sleep(2)
                    res = self.session.get(url, timeout=10)

                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    match = re.search(r'/([A-Za-z]+)-Phone-Number/(\d{8,})', href)
                    if match:
                        c_name = match.group(1).strip()
                        raw_num = match.group(2)
                        formatted_num = f"+{raw_num}"
                        full_url = href if href.startswith("http") else BASE_URL + href
                        flag = get_country_flag(c_name)

                        if not any(n["number"] == formatted_num for n in all_numbers):
                            all_numbers.append({
                                "country": c_name,
                                "flag": flag,
                                "number": formatted_num,
                                "raw_number": raw_num,
                                "url": full_url
                            })

            # Sort to place UK & Canada at the VERY TOP of priority scanning!
            priority_names = ["UK", "United Kingdom", "Canada"]
            all_numbers.sort(key=lambda n: 0 if any(p.lower() in n['country'].lower() for p in priority_names) else 1)

            logging.info(f"⚡ Total Active Phone Numbers Scraped (PRIORITY UK 🇬🇧 & CANADA 🇨🇦): {len(all_numbers)}")
        except Exception as e:
            logging.error(f"Error fetching active numbers: {e}")
        return all_numbers

    def fetch_active_countries(self):
        """Fetch list of active countries derived from scraped active numbers."""
        active_nums = self.fetch_all_active_numbers(max_pages=3)
        countries = []
        for n in active_nums:
            c_name = n["country"]
            if not any(c["name"].lower() == c_name.lower() for c in countries):
                countries.append({
                    "name": c_name,
                    "url": f"https://temporary-phone-number.com/{c_name}-Phone-Number/",
                    "flag": n["flag"]
                })
        return countries

    def fetch_phone_numbers(self, country_url: str):
        """Fetch numbers for a specific country from active numbers list."""
        match = re.search(r'/([A-Za-z]+)-Phone-Number', country_url)
        target_country = match.group(1) if match else ""
        
        all_nums = self.fetch_all_active_numbers(max_pages=4)
        if target_country:
            return [n for n in all_nums if n["country"].lower() == target_country.lower()]
        return all_nums

    def fetch_latest_sms(self, number_dict: dict, country_name: str):
        """Fetch ONLY INSTANT & RECENT incoming SMS for a phone number."""
        messages = []
        url = number_dict["url"]
        phone_number = number_dict["number"]
        flag = get_country_flag(country_name)

        try:
            time.sleep(random.uniform(0.2, 0.4))
            res = self.session.get(url, timeout=8)
            if res.status_code in [403, 429]:
                time.sleep(2)
                res = self.session.get(url, timeout=8)

            if res.status_code != 200:
                return messages

            soup = BeautifulSoup(res.text, "html.parser")

            chat_msgs = soup.find_all("div", class_=re.compile(r'direct-chat-msg', re.I))
            for chat in chat_msgs:
                chat_text = chat.text.strip()
                if "register" in chat_text.lower() and "login" in chat_text.lower():
                    continue
                if "google ads" in chat_text.lower():
                    continue

                if len(chat_text) > 10:
                    time_elem = chat.find("time")
                    time_str = time_elem.text.strip() if time_elem else "Just now"

                    if not is_recent_sms(time_str):
                        continue

                    text_div = chat.find("div", class_="direct-chat-text")
                    clean_msg = text_div.text.strip() if text_div else chat_text

                    service_name = detect_service_name(clean_msg)
                    otp_code = extract_otp_code(clean_msg)

                    messages.append({
                        "country": country_name,
                        "flag": flag,
                        "phone_number": phone_number,
                        "service": service_name,
                        "otp_code": otp_code,
                        "full_text": clean_msg,
                        "time": time_str,
                        "source_url": url
                    })

            if not messages:
                rows = soup.find_all("tr")
                for row in rows:
                    cols = row.find_all(["td", "th"])
                    if len(cols) >= 2:
                        col_texts = [col.text.strip() for col in cols]
                        full_row_text = " ".join(col_texts)
                        if "Status" in full_row_text and "Number" in full_row_text:
                            continue
                        if "Received" in full_row_text or "Active since" in full_row_text:
                            continue

                        msg_text = col_texts[-1] if len(col_texts) > 1 else col_texts[0]
                        time_text = col_texts[0] if len(col_texts) > 1 else "Just now"

                        if not is_recent_sms(time_text):
                            continue

                        if len(msg_text) > 5:
                            service_name = detect_service_name(msg_text)
                            otp_code = extract_otp_code(msg_text)

                            messages.append({
                                "country": country_name,
                                "flag": flag,
                                "phone_number": phone_number,
                                "service": service_name,
                                "otp_code": otp_code,
                                "full_text": msg_text,
                                "time": time_text,
                                "source_url": url
                            })

        except Exception as e:
            pass
        return messages
