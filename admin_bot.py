import logging
import time
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from config import TELEGRAM_BOT_TOKEN, ADMIN_ID, TELEGRAM_GROUP_ID
from database import (
    get_stocked_numbers_by_country, add_user_subscription,
    get_active_subscriptions_for_user, remove_user_subscription,
    remove_all_user_subscriptions, get_top_countries_stats,
    search_sms_db, get_sms_for_number, mark_stocked_announced
)
from scraper import TempPhoneScraper, get_country_flag, COUNTRY_FLAGS
from telegram_notifier import send_group_notice

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

scraper_instance = TempPhoneScraper()

# Helper for main user keyboard
def get_main_user_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Get Number", callback_data="user_get_number"),
         InlineKeyboardButton("📊 Traffic & Live Stats", callback_data="user_traffic")],
        [InlineKeyboardButton("🔖 My Saved Numbers", callback_data="user_my_numbers"),
         InlineKeyboardButton("🔍 Search SMS", callback_data="user_search_sms")],
        [InlineKeyboardButton("❓ Help & Info", callback_data="user_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start & /menu Command Handler
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"

    welcome_text = (
        f"👋 *Welcome {user_name} to Temporary Phone Number Bot!*\n\n"
        "🌐 *Instant Parallel SMS OTP Auto-Forwarder*\n"
        "⚡ Instant SMS reception across 16 active countries & 250+ numbers!\n\n"
        "👇 *Select an option below to start:*"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_user_keyboard()
    )

# /id Command Handler
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg_text = (
        f"📍 *Chat Details:*\n\n"
        f"👤 *User ID:* `{user.id}`\n"
        f"💬 *Chat Title:* {chat.title or 'Private'}\n"
        f"🆔 *Chat ID:* `{chat.id}`\n"
    )
    await update.message.reply_text(msg_text, parse_mode="Markdown")

# /find Command Handler
async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("💡 *Usage:* `/find <service or number>` (e.g. `/find whatsapp`)", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    results = search_sms_db(query, limit=10)

    if not results:
        await update.message.reply_text(f"🔍 No SMS records found for query: `{query}`", parse_mode="Markdown")
        return

    res_text = f"🔎 *SMS Search Results for:* `{query}`\n\n"
    for r in results:
        res_text += (
            f"📱 `{r['phone_number']}` ({r['country']})\n"
            f"👤 Service: *{r['service']}*\n"
            f"🔑 Code: `<code>{r['otp_code']}</code>`\n"
            f"💬 `{r['seen_at']}`\n\n"
        )
    await update.message.reply_text(res_text, parse_mode="Markdown")

# /admin Command Handler (STRICTLY Admin ID 1262396547)
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ *Access Denied!* This command is restricted to Bot Administrator only.", parse_mode="Markdown")
        return

    keyboard = [
        [InlineKeyboardButton("📦 Stocked Numbers Queue", callback_data="admin_stocked_queue")],
        [InlineKeyboardButton("📢 Send Group Notice", callback_data="admin_group_notice")],
        [InlineKeyboardButton("📊 System Traffic", callback_data="user_traffic")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔐 *ADMIN CONTROL PANEL*\n\n"
        f"👑 Administrator ID: `{ADMIN_ID}`\n"
        "⚡ Manage newly stocked numbers, send notices, and view system stats below:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# Callback Query Handler
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # 1. Main Menu
    if data == "user_main_menu":
        await query.edit_message_text(
            "📱 *Temporary Phone Number Bot - Main Menu*\n\nChoose an option below:",
            parse_mode="Markdown",
            reply_markup=get_main_user_keyboard()
        )

    # 2. Get Number -> Country Selector
    elif data == "user_get_number":
        countries = scraper_instance.fetch_active_countries()
        keyboard = []
        row = []
        for c in countries[:16]:
            flag = c.get("flag", "🌐")
            name = c.get("name", "Unknown")
            btn = InlineKeyboardButton(f"{flag} {name}", callback_data=f"sel_c_{name}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="user_main_menu")])

        await query.edit_message_text(
            "🌍 *Select a Country for Temporary Number:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 3. Country Selected -> Number Selector
    elif data.startswith("sel_c_"):
        c_name = data.replace("sel_c_", "")
        countries = scraper_instance.fetch_active_countries()
        c_dict = next((c for c in countries if c["name"].lower() == c_name.lower()), None)
        c_url = c_dict["url"] if c_dict else f"https://temporary-phone-number.com/{c_name}-Phone-Number/"

        numbers = scraper_instance.fetch_phone_numbers(c_url)
        flag = get_country_flag(c_name)

        if not numbers:
            await query.edit_message_text(
                f"⚠️ No active numbers found for {flag} {c_name} currently.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Select Another Country", callback_data="user_get_number")]])
            )
            return

        keyboard = []
        for num in numbers[:10]:
            btn = InlineKeyboardButton(f"📱 {num['number']}", callback_data=f"sel_n_{num['number']}")
            keyboard.append([btn])
        keyboard.append([InlineKeyboardButton("🔙 Back to Countries", callback_data="user_get_number")])

        await query.edit_message_text(
            f"📱 *Select Phone Number for {flag} {c_name}:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 4. Number Selected -> Service Selector
    elif data.startswith("sel_n_"):
        selected_number = data.replace("sel_n_", "")

        services = ["WhatsApp", "Telegram", "Google / Gmail", "Facebook", "TikTok", "OpenAI / ChatGPT"]
        keyboard = []
        row = []
        for s in services:
            btn = InlineKeyboardButton(f"💬 {s}", callback_data=f"sub_{selected_number}_{s}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("⏭️ Skip (All Services)", callback_data=f"sub_{selected_number}_ALL")])
        keyboard.append([InlineKeyboardButton("🔙 Select Another Number", callback_data="user_get_number")])

        await query.edit_message_text(
            f"🎯 *Selected Number:* `{selected_number}`\n\n"
            "👤 *Select Service / App for Private OTP Notification:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 5. Service Selected -> 5-Minute Active Subscription
    elif data.startswith("sub_"):
        parts = data.split("_")
        phone_number = parts[1]
        service_name = parts[2]

        # Add 5-minute active subscription in DB
        add_user_subscription(user_id, phone_number, service_name, duration_seconds=300)

        keyboard = [
            [InlineKeyboardButton("🔍 View Received SMS", callback_data=f"view_sms_{phone_number}")],
            [InlineKeyboardButton("🔄 Change Number", callback_data="user_get_number"),
             InlineKeyboardButton("⏹️ Stop Session", callback_data=f"stop_sub_{phone_number}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]
        ]

        await query.edit_message_text(
            f"🎉 *Number Successfully Activated for 5 Minutes!*\n\n"
            f"📱 *Active Number:* `{phone_number}`\n"
            f"👤 *Service Filter:* *{service_name}*\n"
            f"⏳ *Active Timer:* `5 Minutes (300 Seconds)`\n\n"
            f"⚡ *All incoming SMS for this number will be posted in the Telegram Group and sent privately to your inbox for 5 minutes!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 6. Stop Session
    elif data.startswith("stop_sub_"):
        phone_number = data.replace("stop_sub_", "")
        remove_user_subscription(user_id, phone_number)
        await query.edit_message_text(
            f"⏹️ *Session Stopped for `{phone_number}`.*\n\nIncoming SMS alerts for this session have been turned off.",
            parse_mode="Markdown",
            reply_markup=get_main_user_keyboard()
        )

    # 7. View Received SMS for a Number
    elif data.startswith("view_sms_"):
        phone_number = data.replace("view_sms_", "")
        sms_records = get_sms_for_number(phone_number, limit=8)

        if not sms_records:
            await query.edit_message_text(
                f"📥 *No SMS received yet for `{phone_number}`.*\n\n_Waiting for incoming verification codes..._",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh SMS", callback_data=f"view_sms_{phone_number}")],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]
                ])
            )
            return

        res_text = f"📬 *Received SMS for `{phone_number}`:*\n\n"
        for s in sms_records:
            res_text += (
                f"👤 Service: *{s['service']}*\n"
                f"🔑 OTP Code: `<code>{s['otp_code']}</code>`\n"
                f"💬 Text: `{s['sms_hash'][:15]}...`\n"
                f"⏰ `{s['seen_at']}`\n\n"
            )

        keyboard = [
            [InlineKeyboardButton("🔄 Refresh SMS", callback_data=f"view_sms_{phone_number}")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]
        ]
        await query.edit_message_text(res_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 8. Traffic & Live Stats (Highlighting #1 Most Active Country!)
    elif data == "user_traffic":
        top_countries = get_top_countries_stats()
        hottest_country_text = "🔥 *HIGHEST TRAFFIC COUNTRY:* N/A"
        if top_countries:
            c1 = top_countries[0]
            flag1 = get_country_flag(c1["country"])
            hottest_country_text = f"🔥 *HIGHEST TRAFFIC COUNTRY:* {flag1} *{c1['country']}* ({c1['sms_count']} SMS)"

        stats_text = (
            "📊 *SYSTEM TRAFFIC & LIVE STATS*\n\n"
            f"{hottest_country_text}\n\n"
            "🌐 *Top Active Countries by SMS Volume:*\n"
        )
        for i, c in enumerate(top_countries, start=1):
            flag = get_country_flag(c["country"])
            stats_text += f"{i}. {flag} *{c['country']}* — `{c['sms_count']} SMS`\n"

        stats_text += (
            "\n⚡ *System Highlights:*\n"
            "• Active Countries Scanned: `16 Countries`\n"
            "• Active Phone Numbers: `250+ Numbers`\n"
            "• Scan Speed: `Real-Time Parallel`\n"
        )
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]]
        await query.edit_message_text(stats_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 9. My Saved Numbers with Expiry Countdown & Delete Button
    elif data == "user_my_numbers":
        subs = get_active_subscriptions_for_user(user_id)
        now = int(time.time())

        if not subs:
            await query.edit_message_text(
                "🔖 *My Saved Numbers*\n\nYou currently have no active 5-minute number subscriptions.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Get Number", callback_data="user_get_number")],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]
                ])
            )
            return

        text = "🔖 *My Active Saved Numbers:*\n\n"
        keyboard = []
        for s in subs:
            rem_sec = max(0, s["expires_at"] - now)
            mins = rem_sec // 60
            secs = rem_sec % 60
            text += (
                f"📱 *Number:* `{s['phone_number']}`\n"
                f"👤 Service: *{s['service_name']}*\n"
                f"⏳ Time Remaining: `{mins}m {secs}s`\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(f"🔍 View SMS ({s['phone_number']})", callback_data=f"view_sms_{s['phone_number']}"),
                InlineKeyboardButton(f"❌ Remove", callback_data=f"stop_sub_{s['phone_number']}")
            ])

        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 10. Search SMS (Shows active number's SMS or instructs search)
    elif data == "user_search_sms":
        subs = get_active_subscriptions_for_user(user_id)
        if subs:
            active_num = subs[0]["phone_number"]
            await handle_callback_query(
                Update(update.update_id, callback_query=query),
                context
            )
            return

        search_help = (
            "🔍 *SEARCH SMS OTP CODES*\n\n"
            "You can search past OTP verification codes directly in chat using commands:\n\n"
            "• `/find whatsapp` — Search WhatsApp codes\n"
            "• `/find google` — Search Google verification codes\n"
            "• `/find telegram` — Search Telegram codes\n"
            "• `/find +447848426092` — Search by phone number\n"
        )
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]]
        await query.edit_message_text(search_help, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 11. Help & Info (Cleaned Help text without mentioning /admin)
    elif data == "user_help":
        help_text = (
            "❓ *HELP & BOT INFORMATION*\n\n"
            "1. Click *[ 📱 Get Number ]* to select a temporary number.\n"
            "2. Choose your app/service for private OTP alerts.\n"
            "3. Your session stays active for *5 minutes*.\n"
            "4. Monospace OTP codes can be copied with a *1-click tap*.\n"
            "5. All incoming SMS are posted live in the Telegram Group!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="user_main_menu")]]
        await query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 12. Admin Stocked Numbers Queue (Grouped by Country with 1-Click Post Notice)
    elif data == "admin_stocked_queue":
        if user_id != ADMIN_ID:
            return

        stocked = get_stocked_numbers_by_country()
        if not stocked:
            await query.edit_message_text(
                "📦 *Stocked Numbers Queue*\n\nNo new numbers currently in queue.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="user_admin_back")]])
            )
            return

        text = "📦 *STOCKED NEW NUMBERS BY COUNTRY*\n\n"
        keyboard = []
        for s in stocked:
            c_name = s["country_name"]
            count = s["count"]
            flag = get_country_flag(c_name)
            text += f"{flag} *{c_name}:* `{count} New Numbers`\n"
            keyboard.append([InlineKeyboardButton(f"📢 1-Click Group Post ({flag} {c_name})", callback_data=f"post_notice_{c_name}")])

        keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="user_admin_back")])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # 13. Admin 1-Click Group Notice Announcement
    elif data.startswith("post_notice_"):
        if user_id != ADMIN_ID:
            return

        c_name = data.replace("post_notice_", "")
        flag = get_country_flag(c_name)

        notice_text = (
            f"🎉 <b>NEW NUMBERS ADDED IN {flag} {c_name.upper()}!</b>\n\n"
            f"📱 New numbers for <b>{c_name}</b> are now active and ready for receiving SMS OTP codes!\n"
            f"⚡ Start getting verification codes instantly!"
        )
        send_group_notice(notice_text)

        await query.edit_message_text(
            f"✅ *Announcement notice for {flag} {c_name} successfully posted to Telegram Group!*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="user_admin_back")]])
        )

    # 14. Admin Back
    elif data == "user_admin_back":
        await admin_command(update, context)

def create_admin_app():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN missing!")
        return None

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("search", find_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(handle_callback_query))

    return app
