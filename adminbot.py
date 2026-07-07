#!/usr/bin/env python3
"""
ADMIN BOT - Final
- Approve/Reject payments
- Approve = Premium activate + auto message to user
- Manual premium de bhi sakte ho
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.request import HTTPXRequest

# ============================================================
BOT_TOKEN = "8882071642:AAE7_y-sIkt3To7dxmpJm8vPeZHDKLIn4k0"
ADMIN_IDS = [8602996159]
USER_BOT_TOKEN = "8888869168:AAFAzvTKxIozcpaS3MGx5rPsvAat3fM7N3U"
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

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("💰 Pending Payments", callback_data="admin_payments")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("🎁 Give Premium", callback_data="admin_give_premium")],
        [InlineKeyboardButton("🖼 Change QR", callback_data="admin_qr")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
    ])

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="admin_back")]])


# ============================================================
# PREMIUM ACTIVATION FUNCTION
# ============================================================
async def activate_user_premium(user_id: int, plan: str, username: str = ""):
    """Activate premium for user AND send notification."""
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
    
    # ✅ Send success message to user via USER BOT
    try:
        if USER_BOT_TOKEN:
            from telegram import Bot
            user_bot = Bot(token=USER_BOT_TOKEN)
            
            plan_emoji = {"lifetime": "💎", "yearly": "📅", "monthly": "📅"}
            plan_name = {"lifetime": "Lifetime", "yearly": "Yearly", "monthly": "Monthly"}
            
            msg = (
                f"✅ **Payment Verified Successfully!** 🎉\n\n"
                f"👤 Hello {username}!\n"
                f"💎 Your **{plan_name.get(plan, plan)} Premium** plan is now **ACTIVE**!\n\n"
                f"🚀 Enjoy **unlimited** number lookups!\n"
                f"🔍 Use /lookup to start searching.\n\n"
                f"Thank you for your support! 🙏"
            )
            
            await user_bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
            logger.info(f"✅ Premium activated & notified: User {user_id} - {plan}")
            return True
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
    
    return False


# ============================================================
# HANDLERS
# ============================================================
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    await update.message.reply_text(
        "🛡 **Admin Panel**\n\nSelect option:",
        parse_mode="Markdown",
        reply_markup=admin_menu()
    )


async def admin_dashboard(update, context):
    query = update.callback_query
    await query.answer()
    try:
        db = get_db()
        c = db.cursor()
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        premium = c.execute("SELECT COUNT(*) FROM users WHERE subscription_type IS NOT NULL").fetchone()[0]
        lifetime = c.execute("SELECT COUNT(*) FROM users WHERE subscription_type='lifetime'").fetchone()[0]
        monthly = c.execute("SELECT COUNT(*) FROM users WHERE subscription_type='monthly'").fetchone()[0]
        yearly = c.execute("SELECT COUNT(*) FROM users WHERE subscription_type='yearly'").fetchone()[0]
        pending = c.execute("SELECT COUNT(*) FROM payments WHERE status='pending'").fetchone()[0]
        lookups = c.execute("SELECT COALESCE(SUM(total_lookups),0) FROM users").fetchone()[0]
        db.close()
        
        await query.edit_message_text(
            f"📊 **Dashboard**\n\n"
            f"👥 Total Users: {total}\n"
            f"💎 Premium: {premium}\n"
            f"   ├ Lifetime: {lifetime}\n"
            f"   ├ Yearly: {yearly}\n"
            f"   └ Monthly: {monthly}\n"
            f"💰 Pending: {pending}\n"
            f"🔍 Lookups: {lookups}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_dashboard")],
                [InlineKeyboardButton("◀️ Back", callback_data="admin_back")]
            ])
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=back_btn())


async def admin_users(update, context):
    query = update.callback_query
    await query.answer()
    try:
        db = get_db()
        c = db.cursor()
        users = c.execute("""
            SELECT user_id, username, first_name, COALESCE(subscription_type,'free'), total_lookups, joined_date
            FROM users ORDER BY joined_date DESC LIMIT 30
        """).fetchall()
        db.close()
        
        if not users:
            await query.edit_message_text("❌ No users.", reply_markup=back_btn())
            return
        
        msg = "👥 **Users (30)**\n\n"
        for u in users:
            uid, uname, name, plan, lookups, joined = u
            name = name or "Unknown"
            uname = uname or "N/A"
            badge = "💎" if plan != "free" else "🆓"
            j = joined[:10] if joined else "N/A"
            msg += f"{badge} **{name}** (@{uname})\n   ┣ ID: `{uid}`\n   ┣ {plan} | 🔍{lookups}\n   ┗ {j}\n\n"
            if len(msg) > 3800:
                msg += "\n... (truncated)"
                break
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=back_btn())
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=back_btn())


async def admin_payments(update, context):
    query = update.callback_query
    await query.answer()
    try:
        db = get_db()
        c = db.cursor()
        payments = c.execute("""
            SELECT id, user_id, username, plan, amount, created_at
            FROM payments WHERE status='pending' ORDER BY created_at DESC LIMIT 20
        """).fetchall()
        db.close()
        
        if not payments:
            await query.edit_message_text("✅ **No pending payments!** 🎉", parse_mode="Markdown", reply_markup=back_btn())
            return
        
        msg = f"💰 **Pending: {len(payments)}**\n\n"
        for p in payments[:10]:
            pid, uid, uname, plan, amount, created = p
            c_time = created[:16] if created else "N/A"
            msg += f"🆔 #{pid} | 👤 {uname} (ID: {uid})\n   ┣ 📦 {plan} | ₹{amount}\n   ┗ ⏰ {c_time}\n\n"
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_payments")],
            [InlineKeyboardButton("◀️ Back", callback_data="admin_back")]
        ]))
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=back_btn())


async def admin_give_premium(update, context):
    """Manual premium give option."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎁 **Give Premium Manually**\n\n"
        "Send the user ID and plan like this:\n\n"
        "`GIVE 8602996159 lifetime`\n"
        "`GIVE 8602996159 yearly`\n"
        "`GIVE 8602996159 monthly`\n\n"
        "Or just the user ID to see their info.",
        parse_mode="Markdown",
        reply_markup=back_btn()
    )
    context.user_data["waiting_for_give"] = True


async def approve_payment(payment_id: int, query):
    """Approve payment and activate premium."""
    try:
        db = get_db()
        c = db.cursor()
        payment = c.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        
        if not payment:
            await query.edit_message_text("❌ Payment not found.", reply_markup=back_btn())
            db.close()
            return
        
        user_id, username, plan, amount = payment[1], payment[2], payment[3], payment[4]
        
        # Update payment status
        c.execute("UPDATE payments SET status = 'approved' WHERE id = ?", (payment_id,))
        db.commit()
        db.close()
        
        # ✅ ACTIVATE PREMIUM & SEND MESSAGE
        success = await activate_user_premium(user_id, plan, username)
        
        status = "✅ User notified!" if success else "⚠️ Premium activated but notification failed"
        
        await query.edit_message_text(
            f"✅ **Payment Approved!**\n\n"
            f"#{payment_id} | 👤 {username} (ID: {user_id})\n"
            f"📦 {plan} | ₹{amount}\n\n"
            f"💎 Premium Activated!\n{status}",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )
        
    except Exception as e:
        logger.error(f"Approve error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)[:100]}", reply_markup=back_btn())


async def reject_payment(payment_id: int, query):
    """Reject payment and notify user."""
    try:
        db = get_db()
        c = db.cursor()
        payment = c.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        
        if not payment:
            await query.edit_message_text("❌ Payment not found.", reply_markup=back_btn())
            db.close()
            return
        
        user_id, username, plan, amount = payment[1], payment[2], payment[3], payment[4]
        
        c.execute("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
        db.commit()
        db.close()
        
        # Notify user
        try:
            if USER_BOT_TOKEN:
                from telegram import Bot
                bot = Bot(token=USER_BOT_TOKEN)
                await bot.send_message(
                    chat_id=user_id,
                    text=f"❌ **Payment Rejected**\n\nYour ₹{amount} payment for {plan} was rejected.\nPlease contact admin or try again.",
                    parse_mode="Markdown"
                )
        except:
            pass
        
        await query.edit_message_text(
            f"❌ **Rejected!**\n\n#{payment_id} | 👤 {username} (ID: {user_id})\n📦 {plan} | ₹{amount}\n\nUser notified.",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=back_btn())


async def give_premium_manual(user_id: int, plan: str, query):
    """Manually give premium to any user."""
    try:
        db = get_db()
        c = db.cursor()
        user = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        db.close()
        
        if not user:
            await query.edit_message_text(f"❌ User ID `{user_id}` not found in database.", parse_mode="Markdown", reply_markup=back_btn())
            return
        
        username = user[1] or "User"
        await activate_user_premium(user_id, plan, username)
        
        await query.edit_message_text(
            f"✅ **Premium Given!**\n\n"
            f"👤 {username} (ID: `{user_id}`)\n"
            f"💎 Plan: {plan}\n\n"
            f"User has been notified! 🎉",
            parse_mode="Markdown",
            reply_markup=back_btn()
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}", reply_markup=back_btn())


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    
    # Handle manual premium give
    if text.upper().startswith("GIVE "):
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ Format: `GIVE user_id plan`\nExample: `GIVE 8602996159 lifetime`", parse_mode="Markdown")
            return
        
        try:
            target_id = int(parts[1])
            plan = parts[2].lower()
            if plan not in ["lifetime", "yearly", "monthly"]:
                await update.message.reply_text("❌ Plan must be: lifetime, yearly, or monthly")
                return
            
            db = get_db()
            c = db.cursor()
            user = c.execute("SELECT * FROM users WHERE user_id = ?", (target_id,)).fetchone()
            db.close()
            
            if not user:
                await update.message.reply_text(f"❌ User ID `{target_id}` not found!", parse_mode="Markdown")
                return
            
            await activate_user_premium(target_id, plan, user[1] or "User")
            
            await update.message.reply_text(
                f"✅ **Premium Activated!**\n\n"
                f"👤 User: {user[2] or 'N/A'} (@{user[1] or 'N/A'})\n"
                f"🆔 ID: `{target_id}`\n"
                f"💎 Plan: {plan}\n\n"
                f"📩 User notified successfully!",
                parse_mode="Markdown",
                reply_markup=admin_menu()
            )
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        return
    
    # Handle broadcast
    if context.user_data.get("waiting_for_broadcast"):
        context.user_data["waiting_for_broadcast"] = False
        try:
            db = get_db()
            c = db.cursor()
            users = c.execute("SELECT user_id FROM users").fetchall()
            db.close()
            
            status_msg = await update.message.reply_text(f"📤 Broadcasting to {len(users)} users...")
            
            success = 0
            failed = 0
            if USER_BOT_TOKEN:
                from telegram import Bot
                bot = Bot(token=USER_BOT_TOKEN)
                for (uid,) in users:
                    try:
                        await bot.send_message(chat_id=uid, text=f"📢 **Broadcast**\n\n{text}", parse_mode="Markdown")
                        success += 1
                    except:
                        failed += 1
            
            await status_msg.edit_text(f"✅ **Done!**\n✅ {success} sent\n❌ {failed} failed", reply_markup=admin_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        return


async def admin_change_qr(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🖼 **Send the new QR image**", parse_mode="Markdown", reply_markup=back_btn())
    context.user_data["waiting_for_qr"] = True


async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if context.user_data.get("waiting_for_qr"):
        try:
            photo = update.message.photo[-1]
            file = await photo.get_file()
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_code.jpg")
            await file.download_to_drive(path)
            context.user_data["waiting_for_qr"] = False
            await update.message.reply_text("✅ **QR Updated!**", reply_markup=admin_menu())
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")


async def admin_broadcast(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📢 **Send broadcast message**\nType the message to send to ALL users:",
        parse_mode="Markdown",
        reply_markup=back_btn()
    )
    context.user_data["waiting_for_broadcast"] = True


async def admin_back(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🛡 **Admin Panel**\n\nSelect:", parse_mode="Markdown", reply_markup=admin_menu())


async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if query.from_user.id not in ADMIN_IDS:
        await query.answer("❌ Unauthorized!")
        return
    
    if data == "admin_back":
        await admin_back(update, context)
    elif data == "admin_dashboard":
        await admin_dashboard(update, context)
    elif data == "admin_users":
        await admin_users(update, context)
    elif data == "admin_payments":
        await admin_payments(update, context)
    elif data == "admin_give_premium":
        await admin_give_premium(update, context)
    elif data == "admin_qr":
        await admin_change_qr(update, context)
    elif data == "admin_broadcast":
        await admin_broadcast(update, context)
    elif data.startswith("approve_"):
        pid = int(data.split("_")[1])
        await approve_payment(pid, query)
    elif data.startswith("reject_"):
        pid = int(data.split("_")[1])
        await reject_payment(pid, query)


# ============================================================
# MAIN
# ============================================================
def main():
    req = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(req).build()
    
    app.add_handler(CommandHandler("start", admin_start))
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))
    
    print("✅ ADMIN BOT RUNNING")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()