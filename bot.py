#!/usr/bin/env python3
# bot.py — Telegram admin bot with useful admin commands
# Requires: python-telegram-bot v20+, python-dotenv
# Run: python bot.py

import os
import json
import logging
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise SystemExit("Set TELEGRAM_TOKEN in environment or .env")

ADMIN_IDS = os.getenv("ADMIN_IDS", "")  # comma-separated telegram user IDs
ADMIN_IDS = {int(x) for x in ADMIN_IDS.split(",") if x.strip().isdigit()}

STATE_FILE = "state.json"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- state helpers ---
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"announcements": [], "banned_words": [], "welcome_enabled": True, "welcome_text": "Welcome, {name}!"}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

state = load_state()

# --- admin check decorator ---
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None:
            return
        if (user.id in ADMIN_IDS) or (await is_user_admin(update, user.id)):
            return await func(update, context, *args, **kwargs)
        await update.message.reply_text("Ошибка: доступ только для админов.")
    return wrapper

async def is_user_admin(update: Update, user_id: int) -> bool:
    # Check in chat admins when in group
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        member = await chat.get_member(user_id)
        return member.status in ("administrator", "creator")
    return False

# --- commands ---

@admin_only
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

@admin_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats = context.application.chat_data
    users_tracked = len(context.application.user_data)
    uptime = datetime.utcnow().isoformat() + "Z"
    text = f"Stats:\nTracked chats: {len(chats)}\nTracked users: {users_tracked}\nUptime (now): {uptime}"
    await update.message.reply_text(text)

@admin_only
async def cmd_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /announce message -> save announcement and optionally broadcast to known chats
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Использование: /announce <текст>")
        return
    state["announcements"].append({"text": text, "time": datetime.utcnow().isoformat()})
    save_state(state)
    await update.message.reply_text("Объявление сохранено.")
    # optional: broadcast to chat where command was used
    await update.message.reply_text("Отправляю объявление в этот чат:")
    await update.message.reply_text(text)

@admin_only
async def cmd_list_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = state.get("announcements", [])
    if not items:
        await update.message.reply_text("Нет объявлений.")
        return
    lines = []
    for i, a in enumerate(items, 1):
        t = a.get("time", "")
        txt = a.get("text", "")
        lines.append(f"{i}. [{t}] {txt}")
    await update.message.reply_text("\n\n".join(lines))

@admin_only
async def cmd_clear_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state["announcements"] = []
    save_state(state)
    await update.message.reply_text("Объявления очищены.")

@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /ban <user_id>
    if not context.args:
        await update.message.reply_text("Использование: /ban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Невалидный user_id.")
        return
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        try:
            await chat.ban_member(user_id)
            await update.message.reply_text(f"Пользователь {user_id} заблокирован.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка блокировки: {e}")
    else:
        await update.message.reply_text("Команда должна быть в группе.")

@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /unban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Невалидный user_id.")
        return
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        try:
            await chat.unban_member(user_id)
            await update.message.reply_text(f"Пользователь {user_id} разбанен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Команда должна быть в группе.")

@admin_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /mute <user_id> <minutes>
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /mute <user_id> <minutes>")
        return
    try:
        user_id = int(context.args[0]); minutes = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Невалидные аргументы.")
        return
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        until = datetime.utcnow().timestamp() + minutes * 60
        try:
            await chat.restrict_member(user_id, permissions=ChatPermissions(can_send_messages=False), until_date=int(until))
            await update.message.reply_text(f"Пользователь {user_id} заглушен на {minutes} минут.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Команда должна быть в группе.")

@admin_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /unmute <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Невалидный user_id.")
        return
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        try:
            await chat.restrict_member(user_id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
            await update.message.reply_text(f"Пользователь {user_id} размьючен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Команда должна быть в группе.")

@admin_only
async def cmd_add_banned_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /addword <word>")
        return
    word = context.args[0].lower()
    if word in state["banned_words"]:
        await update.message.reply_text("Слово уже в списке.")
        return
    state["banned_words"].append(word)
    save_state(state)
    await update.message.reply_text(f"Добавлено слово: {word}")

@admin_only
async def cmd_remove_banned_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /removeword <word>")
        return
    word = context.args[0].lower()
    try:
        state["banned_words"].remove(word)
        save_state(state)
        await update.message.reply_text(f"Удалено слово: {word}")
    except ValueError:
        await update.message.reply_text("Слово не найдено.")

@admin_only
async def cmd_list_banned_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = state.get("banned_words", [])
    if not words:
        await update.message.reply_text("Список слов пуст.")
    else:
        await update.message.reply_text("Banned words:\n" + ", ".join(words))

@admin_only
async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /welcome on|off or /welcome <text>
    if not context.args:
        await update.message.reply_text("Использование: /welcome on|off|<text>")
        return
    arg = " ".join(context.args)
    if arg.lower() == "on":
        state["welcome_enabled"] = True
        save_state(state)
        await update.message.reply_text("Приветствие включено.")
        return
    if arg.lower() == "off":
        state["welcome_enabled"] = False
        save_state(state)
        await update.message.reply_text("Приветствие выключено.")
        return
    state["welcome_text"] = arg
    save_state(state)
    await update.message.reply_text("Текст приветствия обновлён.")

@admin_only
async def cmd_getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /getid — покажет id пользователя, упомянутого или отправителя
    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        await update.message.reply_text(f"User id: {uid}")
        return
    if context.args:
        try:
            uid = int(context.args[0]); await update.message.reply_text(f"User id: {uid}")
        except:
            await update.message.reply_text("Невалидный id.")
        return
    await update.message.reply_text(f"Your id: {update.effective_user.id}")

# --- handlers for moderation and welcome ---
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        if state.get("welcome_enabled", True):
            name = m.full_name or m.first_name or "there"
            txt = state.get("welcome_text","Welcome, {name}!").replace("{name}", name)
            await update.message.reply_text(txt)

async def moderate_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lowered = text.lower()
    for w in state.get("banned_words", []):
        if w in lowered:
            try:
                await update.message.delete()
                await update.message.reply_text(f"Сообщение удалено: содержит запрещённое слово.")
            except Exception as e:
                logger.warning("Can't delete message: %s", e)
            return

# --- simple help command ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "/ping — проверить работоспособность (admin)\n"
        "/stats — статистика (admin)\n"
        "/announce <text> — сохранить и отправить объявление (admin)\n"
        "/listann — список объявлений (admin)\n"
        "/clearann — очистить объявления (admin)\n"
        "/ban <user_id> — забанить в чате (admin)\n"
        "/unban <user_id> — разбан (admin)\n"
        "/mute <user_id> <minutes> — заглушить (admin)\n"
        "/unmute <user_id> — размьючить (admin)\n"
        "/addword <word> — добавить запрещённое слово (admin)\n"
        "/removeword <word> — удалить слово (admin)\n"
        "/listwords — список запрещённых слов (admin)\n"
        "/welcome on|off|<text> — настройки приветствия (admin)\n"
        "/getid — получить id пользователя (admin)\n"
        "/help — эта справка\n"
    )
    await update.message.reply_text(text)

# --- main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # commands (admin-only wrapper applied where appropriate)
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("announce", cmd_announce))
    app.add_handler(CommandHandler("listann", cmd_list_announcements))
    app.add_handler(CommandHandler("clearann", cmd_clear_announcements))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))
    app.add_handler(CommandHandler("addword", cmd_add_banned_word))
    app.add_handler(CommandHandler("removeword", cmd_remove_banned_word))
    app.add_handler(CommandHandler("listwords", cmd_list_banned_words))
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("getid", cmd_getid))
    app.add_handler(CommandHandler("help", cmd_help))

    # message handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate_messages))

    print("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
