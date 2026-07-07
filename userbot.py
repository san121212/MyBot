#!/usr/bin/env python3
"""
USER BOT - Full API Fields Show
"""

import os
import sys
import sqlite3
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.request import HTTPXRequest

# ============================================================
BOT_TOKEN = "8888869168:AAFAzvTKxIozcpaS3MGx5rPsvAat3fM7N3U"
ADMIN_BOT_TOKEN = "8882071642:AAE7_y-sIkt3To7dxmpJm8vPeZHDKLIn4k0"
ADMIN_CHAT_ID = 8602996159
API_KEY = None
API_URL = "https://anurag-singh-api45.vercel.app/api/number"
# ============================================================

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "userbot.db")

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            free_credits INTEGER DEFAULT 3,
            subscription_type TEXT DEFAULT NULL,
            subscription_end TEXT DEFAULT NULL,
            total_lookups INTEGER DEFAULT 0,
            joined_date TEXT DEFAULT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            plan TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            screenshot_file_id TEXT,
            created_at TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ============================================================
# HELPERS
# ============================================================
def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def has_premium(user_id):
    user = get_user(user_id)
    if not user:
        return False
    if user[4] == "lifetime":
        return True
    if user[4] and user[5]:
        end = datetime.fromisoformat(user[5])
        if end > datetime.now():
            return True
    return False

def deduct_credit(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT free_credits FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row[0] > 0:
        c.execute("UPDATE users SET free_credits = free_credits - 1, total_lookups = total_lookups + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def activate_plan(user_id, plan):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    if plan == "lifetime":
        c.execute("UPDATE users SET subscription_type = 'lifetime', free_credits = 999999 WHERE user_id = ?", (user_id,))
    elif plan == "yearly":
        end = (now + timedelta(days=365)).isoformat()
        c.execute("UPDATE users SET subscription_type = 'yearly', subscription_end = ?, free_credits = 999999 WHERE user_id = ?", (end, user_id))
    elif plan == "monthly":
        end = (now + timedelta(days=30)).isoformat()
        c.execute("UPDATE users SET subscription_type = 'monthly', subscription_end = ?, free_credits = 999999 WHERE user_id = ?", (end, user_id))
    conn.commit()
    conn.close()

def save_payment(user_id, username, plan, amount, file_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO payments (user_id, username, plan, amount, screenshot_file_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, username, plan, amount, file_id, datetime.now().isoformat()))
    conn.commit()
    pid = c.lastrowid
    conn.close()
    return pid

# ============================================================
# PRICES
# ============================================================
PRICES = {"monthly": 99, "yearly": 999, "lifetime": 1999}
PLAN_NAMES = {"monthly": "📅 Monthly", "yearly": "📅 Yearly", "lifetime": "💎 Lifetime"}

def main_menu(user_id):
    is_premium = has_premium(user_id)
    user = get_user(user_id)
    credits = user[3] if user else 3
    
    status = "💎 Premium" if is_premium else f"🆓 Free ({credits} credits)"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Lookup Number", callback_data="lookup")],
        [InlineKeyboardButton("💎 Buy Plan", callback_data="plans")],
        [InlineKeyboardButton("📊 My Status", callback_data="status")],
    ]
    return InlineKeyboardMarkup(keyboard), status

# ============================================================
# HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username or "N/A", user.first_name or "User")
    keyboard, status = main_menu(user.id)
    
    msg = (
        f"👋 **Namaste {user.first_name}!**\n\n"
        f"🤖 **Number Lookup Bot**\n"
        f"Indian mobile number details nikaalein\n\n"
        f"**Status:** {status}\n\n"
        f"🎁 New users get **3 free credits**!\n"
        f"💎 Subscribe for unlimited lookups.\n\n"
        f"👇 Choose:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)


async def lookup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id, update.effective_user.username or "N/A", update.effective_user.first_name or "User")
    
    has_free = False
    user = get_user(user_id)
    if user and user[3] > 0:
        has_free = True
    
    if not has_premium(user_id) and not has_free:
        await update.message.reply_text(
            "❌ **No credits left!**\n\nBuy a plan to continue:\n📅 Monthly ₹99\n📅 Yearly ₹999\n💎 Lifetime ₹1999",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 View Plans", callback_data="plans")]
            ])
        )
        return
    
    if not context.args:
        await update.message.reply_text("📝 **Enter a 10-digit number:**\nExample: `/lookup 9876543210`", parse_mode="Markdown")
        return
    
    phone = context.args[0].strip()
    await process_number(update, context, phone, user_id)


async def process_number(update, context, phone, user_id):
    phone = phone.replace("+91", "").replace(" ", "")
    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("❌ Invalid number! Enter 10 digits.")
        return
    
    status_msg = await update.message.reply_text(f"🔍 Searching for `{phone}`...", parse_mode="Markdown")
    
    try:
        params = {"num": phone}
        if API_KEY: params["key"] = API_KEY
        resp = requests.get(API_URL, params=params, timeout=15)
        data = resp.json()
    except Exception as e:
        await status_msg.edit_text(f"❌ API Error: {str(e)[:100]}")
        return
    
    # Deduct credit if free user
    if not has_premium(user_id):
        deduct_credit(user_id)
    
    if not data.get("success"):
        await status_msg.edit_text(f"❌ {data.get('message', 'Error')}")
        return
    
    results = data.get("results", [])
    total = data.get("total", len(results))
    
    # Build header
    lines = [f"📞 **Number:** `{data.get('number', phone)}`"]
    lines.append(f"📊 **Total Results:** {total}")
    
    # Truecaller name (top level)
    tc_name = data.get("truecaller_name")
    if tc_name and tc_name != "N/A":
        lines.append(f"📛 **Truecaller:** {tc_name}")
    
    # Cached info
    if data.get("cached"):
        lines.append(f"💾 **Cached:** Yes")
    
    lines.append("═" * 20)
    
    # Build each entry with ALL available fields
    for i, entry in enumerate(results, 1):
        lines.append(f"\n── **Entry {i}** ──")
        
        # Mobile number
        if entry.get("mobile"):
            lines.append(f"📱 **Mobile:** `{entry['mobile']}`")
        
        # Name
        if entry.get("name") and entry['name'] != "N/A":
            lines.append(f"👤 **Name:** {entry['name']}")
        
        # Father's name / Fname
        if entry.get("fname") and entry['fname'] != "N/A":
            lines.append(f"👨 **Father:** {entry['fname']}")
        
        # Truecaller name from entry
        if entry.get("truecaller_name") and entry['truecaller_name'] != "N/A":
            lines.append(f"📛 **Truecaller:** {entry['truecaller_name']}")
        
        # Address
        if entry.get("address") and entry['address'] != "N/A":
            addr = entry['address'][:100]
            lines.append(f"🏠 **Address:** {addr}")
        
        # Circle
        if entry.get("circle") and entry['circle'] != "N/A":
            lines.append(f"📡 **Circle:** {entry['circle']}")
        
        # Email
        if entry.get("email") and entry['email'] != "N/A":
            lines.append(f"📧 **Email:** {entry['email']}")
        
        # ID / Aadhaar reference
        if entry.get("id") and entry['id'] != "N/A":
            lines.append(f"🆔 **ID/aadhar:** `{entry['id']}`")
        
        # Alternate number
        if entry.get("alt") and entry['alt'] != "N/A":
            lines.append(f"📞 **Alt No:** `{entry['alt']}`")
        
        # Provider / Operator if available
        if entry.get("operator") and entry['operator'] != "N/A":
            lines.append(f"📡 **Operator:** {entry['operator']}")
        if entry.get("provider") and entry['provider'] != "N/A":
            lines.append(f"📡 **Provider:** {entry['provider']}")
    
    result = "\n".join(lines)
    
    # Credit info
    if not has_premium(user_id):
        user = get_user(user_id)
        result += f"\n\n🟡 **Remaining credits:** {user[3]}"
    
    # Delete status message
    await status_msg.delete()
    
    # Send result (split if needed)
    MAX_CHARS = 3900
    if len(result) > MAX_CHARS:
        # Send in chunks
        parts = [result[i:i+MAX_CHARS] for i in range(0, len(result), MAX_CHARS)]
        for part in parts:
            await update.message.reply_text(part, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            result,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Another Lookup", callback_data="lookup"),
                 InlineKeyboardButton("💎 Buy Plan", callback_data="plans")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        return  # already sent with buttons, skip below
    
    # Send action buttons if we split
    await update.message.reply_text(
        "✅ **Lookup complete!**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Another Lookup", callback_data="lookup"),
             InlineKeyboardButton("💎 Buy Plan", callback_data="plans")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    )


# ============================================================
# PLANS & PAYMENT
# ============================================================
QR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_code.jpg")

async def show_plans(update, context):
    msg = (
        "💎 **Choose Your Plan**\n\n"
        "📅 **Monthly** — ₹99 (30 days)\n"
        "📅 **Yearly** — ₹999 (365 days)\n"
        "💎 **Lifetime** — ₹1999 (Never expire)\n\n"
        "👇 Select:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Monthly ₹99", callback_data="plan_monthly")],
        [InlineKeyboardButton("📅 Yearly ₹999", callback_data="plan_yearly")],
        [InlineKeyboardButton("💎 Lifetime ₹1999", callback_data="plan_lifetime")],
        [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]
    ])
    if update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=kb)


async def select_plan(update, context):
    query = update.callback_query
    await query.answer()
    
    plan = query.data.replace("plan_", "")
    amount = PRICES[plan]
    name = PLAN_NAMES[plan]
    
    msg = f"{name}\n💰 **Amount: ₹{amount}**\n\n📸 Send payment screenshot after UPI transfer."
    
    try:
        with open(QR_PATH, "rb") as f:
            await query.edit_message_text(f"{name} — ₹{amount}\n\nScan QR and pay:", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Back", callback_data="plans")]
            ]))
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=f,
                caption=f"💳 Pay ₹{amount} for {name}\nSend screenshot after payment!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Sent Payment", callback_data=f"pay_{plan}")]
                ])
            )
    except FileNotFoundError:
        context.user_data["selected_plan"] = plan
        context.user_data["selected_amount"] = amount
        context.user_data["waiting_for_screenshot"] = True
        await query.edit_message_text(
            f"{msg}\n\n(QR not found, send screenshot directly)",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="plans")]])
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    
    if not context.user_data.get("waiting_for_screenshot"):
        await update.message.reply_text("Please select a plan first with 💎 Buy Plan")
        return
    
    plan = context.user_data.get("selected_plan", "monthly")
    amount = context.user_data.get("selected_amount", 99)
    file_id = update.message.photo[-1].file_id
    
    pid = save_payment(user_id, username, plan, amount, file_id)
    
    try:
        from telegram import Bot
        admin_bot = Bot(token=ADMIN_BOT_TOKEN)
        caption = (
            f"🆕 **New Payment Request**\n\n"
            f"👤 **User:** {username} (ID: {user_id})\n"
            f"📦 **Plan:** {PLAN_NAMES[plan]}\n"
            f"💰 **Amount:** ₹{amount}\n"
            f"🆔 **ID:** #{pid}"
        )
        await admin_bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{pid}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pid}")
                ]
            ])
        )
    except Exception as e:
        logger.error(f"Admin notify failed: {e}")
    
    context.user_data["waiting_for_screenshot"] = False
    
    await update.message.reply_text(
        f"✅ **Payment request sent!**\n\n"
        f"📦 {PLAN_NAMES[plan]}\n"
        f"💰 ₹{amount}\n"
        f"🆔 Request #{pid}\n\n"
        f"⏳ Admin will verify soon. You'll be notified! 🎉",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]])
    )


async def show_status(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]))
        return
    
    is_prem = has_premium(user_id)
    status = "💎 **Premium Active**" if is_prem else f"🟡 **Free** ({user[3]} credits)"
    
    msg = (
        f"📊 **Your Status**\n\n"
        f"👤 {query.from_user.first_name}\n"
        f"📈 {status}\n"
        f"🔍 Total Lookups: {user[6]}\n"
        f"📅 Joined: {user[7][:10] if user[7] else 'N/A'}\n"
        f"💎 Plan: {user[4] or 'Free'}"
    )
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Buy Plan", callback_data="plans")],
        [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]
    ]))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "main_menu":
        await query.answer()
        keyboard, status = main_menu(user_id)
        await query.edit_message_text(f"👋 **Menu**\n\n**Status:** {status}\n\n👇 Choose:", parse_mode="Markdown", reply_markup=keyboard)
    elif data == "lookup":
        await query.answer()
        await query.edit_message_text("📝 **Enter a 10-digit number:**\nJust type below 👇", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]))
        context.user_data["waiting_for_number"] = True
    elif data == "plans":
        await show_plans(update, context)
    elif data == "status":
        await show_status(update, context)
    elif data.startswith("plan_"):
        await select_plan(update, context)
    elif data.startswith("pay_"):
        plan = data.replace("pay_", "")
        context.user_data["selected_plan"] = plan
        context.user_data["selected_amount"] = PRICES[plan]
        context.user_data["waiting_for_screenshot"] = True
        await query.answer()
        await query.edit_message_text(f"📸 Now send the **payment screenshot** here.\n\n💰 {PLAN_NAMES[plan]} — ₹{PRICES[plan]}", parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get("waiting_for_number"):
        context.user_data["waiting_for_number"] = False
        await process_number(update, context, text, user_id)
        return
    
    cleaned = text.replace("+91", "").replace(" ", "")
    if cleaned.isdigit() and len(cleaned) == 10:
        await process_number(update, context, cleaned, user_id)
        return
    
    await update.message.reply_text("Type /start for menu or /lookup 9876543210")


# ============================================================
# MAIN
# ============================================================
def main():
    req = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lookup", lookup_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ USER BOT RUNNING (Full API Fields)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()