# 📱 Temporary Phone Number Telegram Auto-Forwarder & Bot

A 24/7 continuous parallel multi-country SMS OTP scraper and interactive Telegram bot.

---

## ⚡ Features

1. **Instant SMS Forwarding:**
   - Scrapes 90+ active phone numbers across **UK (`🇬🇧`)**, **Canada (`🇨🇦`)**, **US (`🇺🇸`)**, **Finland (`🇫🇮`)**, **Netherlands (`🇳🇱`)**, **Sweden (`🇸🇪`)**, etc.
   - Forwards fresh incoming SMS OTP codes directly to your Telegram Group (`-1003922823297`).

2. **Full Unmasked OTP Codes:**
   - Authenticates on `temporary-phone-number.com` via MD5 hashing to unlock full numeric OTP codes (no `****`).
   - Monospace 1-click tap-to-copy OTP formatting (`<code>123456</code>`).

3. **5-Minute Private User Subscriptions:**
   - Users can select a number and service via `[ 📱 Get Number ]`.
   - The bot forwards all incoming OTPs for that number directly to the user's private Telegram inbox for 5 minutes.
   - UI controls: `[ ⏹️ Stop Session ]`, `[ 🔄 Change Number ]`, `[ 🔍 View Received SMS ]`.

4. **Strict Admin Control Panel (`/admin`):**
   - Restricted to Admin ID `1262396547`.
   - 1-Click Announcement broadcast to Telegram Group when new numbers arrive.
   - Real-time country traffic highlights.

---

## 🚀 Cloud Deployment Instructions (Railway / Render / Koyeb)

### Option A: Deploy on Railway.app (Recommended)
1. Push this repository to GitHub.
2. Go to [Railway.app](https://railway.app) and click **New Project** -> **Deploy from GitHub repo**.
3. Add Environment Variables in Railway settings:
   - `TELEGRAM_BOT_TOKEN`: `8977584755:AAH-KcUCgqKXexuYQfZa-BOO74atkDgtEcI`
   - `TELEGRAM_GROUP_ID`: `-1003922823297`
   - `ADMIN_ID`: `1262396547`
   - `LOGIN_EMAIL`: `mithuchandra647@gmail.com`
   - `LOGIN_PASSWORD`: `Mithu@808`
4. Click **Deploy**!

### Option B: Deploy on Render.com
1. Push repository to GitHub.
2. Go to [Render.com](https://render.com) and click **New** -> **Background Worker**.
3. Connect your GitHub repository.
4. Set Build Command: `pip install -r requirements.txt`
5. Set Start Command: `python main.py`
6. Add Environment Variables in Render dashboard and click **Deploy**.

---

## 🛠️ Local Running
```bash
python main.py
```
