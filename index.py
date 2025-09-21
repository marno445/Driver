import json, os, asyncio, traceback, base64, requests
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================ CONFIG ================
TOKEN = "8119841485:AAHYI5tjYih6apIV-8Xn2sYtRh2nvWuWB68"

# GITHUB CONFIG
GITHUB_TOKEN = "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"   # ← ganti dengan Personal Access Token kamu
REPO = "marno445/DatabaseRose"    # format: username/repo
DB_FILE = "Database.json"     # nama file di repo

LOG_CHANNEL = -1002983936322
OWNER_ID = 7853514708

# ================ UTILS ================
def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def load_json(file, default):
    url = f"https://api.github.com/repos/{REPO}/contents/{file}"
    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode()
        return json.loads(content)
    else:
        return default

def save_json(file, data):
    url = f"https://api.github.com/repos/{REPO}/contents/{file}"
    r = requests.get(url, headers=github_headers())
    sha = r.json()["sha"] if r.status_code == 200 else None

    new_content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    payload = {
        "message": f"Update {file}",
        "content": new_content,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=github_headers(), json=payload)
    if r.status_code not in [200, 201]:
        print("❌ Gagal save ke GitHub:", r.text)

def is_private_chat(update: Update):
    return update.effective_chat.type == "private"

def get_bot_speed(start_time):
    delta = (datetime.now() - start_time).total_seconds() * 1000
    return round(delta, 2)

async def safe_edit(chat_id, message_id, text, keyboard=None, bot=None):
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
            parse_mode="HTML"
        )
    except Exception as e:
        print("Edit error:", e)

# (LANJUTKAN semua kode dari /start, button, handle_media, bcuser, dll. persis seperti yang kamu kasih — tidak perlu diubah)

# ================ ERROR LOGGER ================
async def log_error(update, context, level="tinggi"):
    error_text = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    log_id = int(datetime.now().timestamp())
    log_data = f"📝 Detail log #{log_id}\n\n{error_text}"
    with open("error.log", "a") as f:
        f.write(f"\n[{datetime.now()}] {log_data}\n")

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("📖 Lihat", callback_data=f"showlog_{log_id}")]])
    await context.bot.send_message(
        chat_id=LOG_CHANNEL,
        text=f"⚠️ Log error\nType: {level}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=btn
    )
    context.chat_data[f"log_{log_id}"] = log_data

# ================ COMMAND /start ================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        await update.message.reply_text(
            "⚠️ This bot can only be used in <b>private chat</b>",
            parse_mode="HTML"
        )
        return

    start_time = datetime.now()
    db = load_json(DB_FILE, {"users": {}, "links": {}})
    args = context.args

    # Statistik
    total_users = len(db.get("users", {}))
    total_links = len(db.get("links", {}))
    speed = get_bot_speed(start_time)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Simpan user baru
    user_id = str(update.effective_user.id)
    if user_id not in db["users"]:
        db["users"][user_id] = {"joined": current_time}
        save_json(DB_FILE, db)

    # Jika ada argumen, buka file yang dibagikan
    if args:
        link_id = args[0]
        link = db["links"].get(link_id)
        if not link:
            await update.message.reply_text("❌ Link not found")
            return
        caption = f"🔗 {link['name']}"

        if link["type"] == "photo":
            await update.message.reply_photo(link["file_id"], caption=caption)
        elif link["type"] == "video":
            await update.message.reply_video(link["file_id"], caption=caption)
        elif link["type"] == "document":
            await update.message.reply_document(link["file_id"], caption=caption)
        elif link["type"] == "audio":
            await update.message.reply_audio(link["file_id"], caption=caption)
        elif link["type"] == "voice":
            await update.message.reply_voice(link["file_id"], caption=caption)
        return

    # Pesan utama
    stats_text = (
        f"👋 <b>Welcome to RoseShareBot!</b>\n\n"
        f"⚡ <b>Ping:</b> {speed} ms\n"
        f"🕒 <b>Time:</b> {current_time}\n"
        f"👥 <b>Active Users:</b> {total_users}\n"
        f"📂 <b>Link Created:</b> {total_links}"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Create", callback_data="create"),
         InlineKeyboardButton("📂 List", callback_data="list")],
        [InlineKeyboardButton("🔍 Search", callback_data="search")]
    ]

    msg = await update.message.reply_photo(
        "https://files.catbox.moe/kujis2.jpg",
        caption=stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    context.chat_data["main_msg_id"] = msg.message_id

# ================ BUTTON HANDLER ================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_json(DB_FILE, {"users": {}, "links": {}})
    main_id = context.chat_data.get("main_msg_id")
    chat_id = query.message.chat_id
    user_id = str(query.from_user.id)
    user = db["users"].setdefault(user_id, {})

    if not main_id:
        await query.answer("⚠️ Type /start to restart.", show_alert=True)
        return

    # Create Link
    if query.data == "create":
        user["state"] = "waiting_media"
        save_json(DB_FILE, db)
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
        await safe_edit(chat_id, main_id, "📤 Send media", keyboard, context.bot)

    # List Link
    elif query.data == "list":
        user_links = [name for name, data in db["links"].items() if str(data["owner"]) == user_id]
        if not user_links:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
            await safe_edit(chat_id, main_id, "📂 You haven't created a link yet", keyboard, context.bot)
            return
        keyboard = [[InlineKeyboardButton(name[:30], callback_data=f"link_{name}")] for name in user_links]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
        await safe_edit(chat_id, main_id, "📂 List your links", keyboard, context.bot)

    # Search Link
    elif query.data == "search":
        user["state"] = "searching"
        save_json(DB_FILE, db)
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
        await safe_edit(chat_id, main_id, "🔍 Send the name of the link you want to search for:", keyboard, context.bot)

    # Menu Utama
    elif query.data == "menu":
        user["state"] = None
        user.pop("temp_media", None)
        user.pop("edit_target", None)
        save_json(DB_FILE, db)

        start_time = datetime.now()
        total_users = len(db.get("users", {}))
        total_links = len(db.get("links", {}))
        speed = get_bot_speed(start_time)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        stats_text = (
            f"👋 <b>Welcome to RoseShareBot!</b>\n\n"
            f"⚡ <b>Ping:</b> {speed} ms\n"
            f"🕒 <b>Time:</b> {current_time}\n"
            f"👥 <b>Active Users:</b> {total_users}\n"
            f"📂 <b>Link Created:</b> {total_links}"
        )

        keyboard = [
            [InlineKeyboardButton("➕ Create", callback_data="create"),
             InlineKeyboardButton("📂 List", callback_data="list")],
            [InlineKeyboardButton("🔍 Search", callback_data="search")]
        ]

        await context.bot.edit_message_media(
            chat_id=chat_id,
            message_id=main_id,
            media=InputMediaPhoto(
                media="https://files.catbox.moe/kujis2.jpg",
                caption=stats_text,
                parse_mode="HTML"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Detail Link
    elif query.data.startswith("link_"):
        name = query.data.split("_", 1)[1]
        link = db["links"].get(name)
        if not link:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
            await safe_edit(chat_id, main_id, "❌ Link not found", keyboard, context.bot)
            return

        bot_username = (await context.bot.get_me()).username
        detail = (
            f"📌 <b>Media Details:</b>\n\n"
            f"🆔 Name: <code>{link['name']}</code>\n"
            f"👤 Owner: <code>{link['owner']}</code>\n"
            f"🕒 Time: <code>{link['time']}</code>\n"
            f"📂 Type: <code>{link['type']}</code>\n"
            f"🔗 <a href='https://t.me/{bot_username}?start={link['name']}'>Open Link</a>"
        )

        if str(link['owner']) == user_id:
            keyboard = [
                [InlineKeyboardButton("📤 View Media", callback_data=f"view_{name}")],
                [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{name}"),
                 InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{name}")],
                [InlineKeyboardButton("🔙 Back", callback_data="list")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📤 View Media", callback_data=f"view_{name}")],
                [InlineKeyboardButton("🔙 Back", callback_data="menu")]
            ]

        await safe_edit(chat_id, main_id, detail, keyboard, context.bot)

    # Lihat Link
    elif query.data.startswith("view_"):
        name = query.data.split("_", 1)[1]
        link = db["links"].get(name)
        if not link:
            await query.answer("❌ Link not found", show_alert=True)
            return

        if link["type"] == "photo":
            await context.bot.send_photo(chat_id, link["file_id"], caption=link["name"])
        elif link["type"] == "video":
            await context.bot.send_video(chat_id, link["file_id"], caption=link["name"])
        elif link["type"] == "document":
            await context.bot.send_document(chat_id, link["file_id"], caption=link["name"])
        elif link["type"] == "audio":
            await context.bot.send_audio(chat_id, link["file_id"], caption=link["name"])
        elif link["type"] == "voice":
            await context.bot.send_voice(chat_id, link["file_id"], caption=link["name"])
        await query.answer("📤 File dikirim!")

    # Edit Link
    elif query.data.startswith("edit_"):
        name = query.data.split("_", 1)[1]
        if name not in db["links"]:
            await query.answer("❌ Link not found", show_alert=True)
            return
        user["state"] = "renaming"
        user["edit_target"] = name
        save_json(DB_FILE, db)
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="list")]]
        await safe_edit(chat_id, main_id, "✏️ Submit new name", keyboard, context.bot)
        await query.answer("Mode edit aktif!")

    # Delete Link
    elif query.data.startswith("delete_"):
        name = query.data.split("_", 1)[1]
        if name in db["links"]:
            db["links"].pop(name)
            save_json(DB_FILE, db)
            await query.answer("🗑 Link removed!", show_alert=True)

            # Update daftar link
            user_links = [n for n, data in db["links"].items() if str(data["owner"]) == user_id]
            keyboard = [[InlineKeyboardButton(n[:30], callback_data=f"link_{n}")] for n in user_links]
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
            await safe_edit(chat_id, main_id, "📂 List your links", keyboard, context.bot)
        else:
            await query.answer("❌ Link not found", show_alert=True)

# ================ HANDLE MEDIA & TEXT ================
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_json(DB_FILE, {"users": {}, "links": {}})
    user_id = str(update.effective_user.id)
    user = db["users"].get(user_id, {})
    main_id = context.chat_data.get("main_msg_id")
    chat_id = update.message.chat_id
    msg = update.message

    # Tidak ada state aktif
    if not user.get("state"):
        return

    # Saat user mengirim media
    if user["state"] == "waiting_media" and msg.text is None:
        file_id, media_type = None, None
        if msg.photo: file_id, media_type = msg.photo[-1].file_id, "photo"
        elif msg.video: file_id, media_type = msg.video.file_id, "video"
        elif msg.document: file_id, media_type = msg.document.file_id, "document"
        elif msg.audio: file_id, media_type = msg.audio.file_id, "audio"
        elif msg.voice: file_id, media_type = msg.voice.file_id, "voice"
        else:
            await msg.reply_text("❌ Unsupported format")
            return

        user["temp_media"] = {
            "file_id": file_id,
            "type": media_type,
            "owner": update.effective_user.id
        }
        user["state"] = "waiting_name"
        save_json(DB_FILE, db)
        await msg.delete()
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
        await safe_edit(chat_id, main_id, "📝 send link name", keyboard, context.bot)
        return

    # Saat search link
    if user.get("state") == "searching" and msg.text:
        keyword = msg.text.strip().lower()
        await msg.delete()

        results = [name for name in db["links"].keys() if keyword in name.lower()]
        if not results:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
            await safe_edit(chat_id, main_id, f"❌ No links match the name: <b>{keyword}</b>", keyboard, context.bot)
            return

        keyboard = [[InlineKeyboardButton(name[:30], callback_data=f"link_{name}")] for name in results[:10]]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])
        await safe_edit(chat_id, main_id, f"🔍 Search results: <b>{keyword}</b>", keyboard, context.bot)
        return

    # Saat create atau rename
    if msg.text and user.get("state") in ["waiting_name", "renaming"]:
        link_name = msg.text.strip()

        if " " in link_name:
            await msg.reply_text("❌ Names must not contain spaces")
            return

        if not link_name.isalnum():
            await msg.reply_text("❌ Names can only be letters and numbers without symbols")
            return

        if link_name in db["links"]:
            await msg.reply_text("❌ Link name already in use, please use another name")
            return

        if user["state"] == "waiting_name":
            media = user.pop("temp_media")
            db["links"][link_name] = {
                "file_id": media["file_id"],
                "type": media["type"],
                "owner": media["owner"],
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": link_name
            }
            user["state"] = None
            save_json(DB_FILE, db)
            await msg.delete()
            bot_username = (await context.bot.get_me()).username
            share_link = f"https://t.me/{bot_username}?start={link_name}"
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
            await safe_edit(chat_id, main_id, f"✅ Link created successfully!\n\n🔗 {share_link}", keyboard, context.bot)

        elif user["state"] == "renaming":
            old_name = user.pop("edit_target")
            link = db["links"].pop(old_name, None)
            if link:
                link["name"] = link_name
                db["links"][link_name] = link
            user["state"] = None
            save_json(DB_FILE, db)
            await msg.delete()
            bot_username = (await context.bot.get_me()).username
            share_link = f"https://t.me/{bot_username}?start={link_name}"
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu")]]
            await safe_edit(chat_id, main_id, f"✏️ Link created successfully!\n\n🔗 {share_link}", keyboard, context.bot)

# ================ BROADCAST ================
async def bcuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sender_id = update.effective_user.id

    if sender_id != OWNER_ID:
        await update.message.reply_text("❌ You do not have permission to use this command.")
        return

    db = load_json(DB_FILE, {"users": {}, "links": {}})
    users = list(db.get("users", {}).keys())

    if not context.args:
        await update.message.reply_text("⚠️ Format: <code>/bcuser teks_pesan</code>", parse_mode="HTML")
        return

    # Gabungkan semua argumen menjadi teks pesan broadcast
    broadcast_message = " ".join(context.args)

    await update.message.reply_text(
        f"📢 Memulai broadcast ke <b>{len(users)}</b> pengguna...",
        parse_mode="HTML"
    )

    sent = 0
    failed = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=broadcast_message)
            sent += 1
            await asyncio.sleep(0.10)  # Delay agar tidak diblokir Telegram
        except Exception as e:
            print(f"Gagal kirim ke {uid}: {e}")
            failed += 1

    await update.message.reply_text(
        f"✅ <b>Broadcast selesai!</b>\n\n"
        f"Berhasil: <code>{sent}</code>\n"
        f"Gagal: <code>{failed}</code>",
        parse_mode="HTML"
    )

# ================ MAIN ================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bcuser", bcuser))

    # Callback Button
    app.add_handler(CallbackQueryHandler(button))

    # Message Handler (teks dan media)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_media))
    app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT, handle_media))

    # Error Handler
    app.add_error_handler(log_error)

    print("🤖 Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()

