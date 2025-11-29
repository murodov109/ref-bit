import os
import json
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

app = Client("kino_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DATA_FILE = "database.json"
temp_data = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "films": {},
        "admins": [],
        "users": [],
        "channels": [],
        "request_channel": None,
        "url_links": []
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

def is_admin(user_id):
    return user_id == OWNER_ID or user_id in data["admins"]

async def check_subscription(client, user_id):
    not_subscribed = []
    
    for ch in data["channels"]:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
                not_subscribed.append(ch)
        except:
            not_subscribed.append(ch)
    
    return not_subscribed

def admin_panel_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Film qo'shish"), KeyboardButton("🗑 Film o'chirish")],
        [KeyboardButton("👤 Admin qo'shish"), KeyboardButton("❌ Admin o'chirish")],
        [KeyboardButton("📢 Reklama tarqatish")],
        [KeyboardButton("📺 Majburiy obuna"), KeyboardButton("📨 Zayafka kanal")],
        [KeyboardButton("🔗 URL link"), KeyboardButton("📊 Statistika")]
    ], resize_keyboard=True)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)
    
    if is_admin(user_id):
        await message.reply_text(
            f"👋 Salom {message.from_user.first_name}!\n\n"
            "🎛️ Admin panel:",
            reply_markup=admin_panel_keyboard()
        )
        return
    
    not_sub = await check_subscription(client, user_id)
    
    if not_sub:
        buttons = []
        
        for ch in not_sub:
            try:
                chat = await client.get_chat(ch)
                buttons.append([InlineKeyboardButton(f"📢 {chat.title}", url=f"https://t.me/{chat.username if chat.username else ch}")])
            except:
                pass
        
        buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
        
        await message.reply_text(
            "❗️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    if data["request_channel"] or data["url_links"]:
        extra_buttons = []
        
        if data["request_channel"]:
            try:
                chat = await client.get_chat(data["request_channel"])
                extra_buttons.append([InlineKeyboardButton(f"📨 {chat.title}", url=f"https://t.me/{chat.username if chat.username else data['request_channel']}")])
            except:
                pass
        
        for link in data["url_links"]:
            extra_buttons.append([InlineKeyboardButton(f"🔗 {link['name']}", url=link['url'])])
        
        if extra_buttons:
            extra_buttons.append([InlineKeyboardButton("✅ Davom etish", callback_data="continue")])
            
            await message.reply_text(
                "🎬 Botdan to'liq foydalanish uchun qo'shimcha kanallarga ham obuna bo'ling:",
                reply_markup=InlineKeyboardMarkup(extra_buttons)
            )
            return
    
    await message.reply_text(
        f"👋 Salom {message.from_user.first_name}!\n\n"
        "🎬 Siz bu bot orqali istalgan film kodini kiritib topishingiz mumkin.\n\n"
        "🎥 Eng so'ngi premyeralar bizda!\n\n"
        "📝 Film kodini yuboring:",
        reply_markup=ReplyKeyboardRemove()
    )

@app.on_callback_query(filters.regex("check_sub"))
async def check_sub_handler(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    not_sub = await check_subscription(client, user_id)
    
    if not_sub:
        await callback.answer("❌ Siz hali majburiy kanallarga obuna bo'lmadingiz!", show_alert=True)
        return
    
    await callback.message.delete()
    
    if data["request_channel"] or data["url_links"]:
        extra_buttons = []
        
        if data["request_channel"]:
            try:
                chat = await client.get_chat(data["request_channel"])
                extra_buttons.append([InlineKeyboardButton(f"📨 {chat.title}", url=f"https://t.me/{chat.username if chat.username else data['request_channel']}")])
            except:
                pass
        
        for link in data["url_links"]:
            extra_buttons.append([InlineKeyboardButton(f"🔗 {link['name']}", url=link['url'])])
        
        if extra_buttons:
            extra_buttons.append([InlineKeyboardButton("✅ Davom etish", callback_data="continue")])
            
            await callback.message.reply_text(
                "🎬 Botdan to'liq foydalanish uchun qo'shimcha kanallarga ham obuna bo'ling:",
                reply_markup=InlineKeyboardMarkup(extra_buttons)
            )
            return
    
    await callback.message.reply_text(
        f"✅ Obuna tasdiqlandi!\n\n"
        f"👋 Salom {callback.from_user.first_name}!\n\n"
        "🎬 Siz bu bot orqali istalgan film kodini kiritib topishingiz mumkin.\n\n"
        "🎥 Eng so'ngi premyeralar bizda!\n\n"
        "📝 Film kodini yuboring:"
    )

@app.on_callback_query(filters.regex("continue"))
async def continue_handler(client, callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.reply_text(
        f"👋 Salom {callback.from_user.first_name}!\n\n"
        "🎬 Siz bu bot orqali istalgan film kodini kiritib topishingiz mumkin.\n\n"
        "🎥 Eng so'ngi premyeralar bizda!\n\n"
        "📝 Film kodini yuboring:"
    )
    await callback.answer()

@app.on_message(filters.private & filters.text)
async def message_handler(client, message: Message):
    user_id = message.from_user.id
    text = message.text
    
    if not is_admin(user_id):
        not_sub = await check_subscription(client, user_id)
        if not_sub:
            buttons = []
            
            for ch in not_sub:
                try:
                    chat = await client.get_chat(ch)
                    buttons.append([InlineKeyboardButton(f"📢 {chat.title}", url=f"https://t.me/{chat.username if chat.username else ch}")])
                except:
                    pass
            
            buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
            
            await message.reply_text(
                "❗️ Botdan foydalanish uchun majburiy kanallarga obuna bo'ling:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
    
    if user_id in temp_data:
        action = temp_data[user_id]["action"]
        
        if action == "add_film":
            step = temp_data[user_id].get("step")
            
            if step == "name":
                temp_data[user_id]["name"] = text
                temp_data[user_id]["step"] = "code"
                await message.reply_text("🔢 Kino kodini yozing:")
            
            elif step == "code":
                code = text.strip()
                if code in data["films"]:
                    await message.reply_text("❌ Bu kod band! Boshqa kod kiriting:")
                    return
                
                data["films"][code] = {
                    "name": temp_data[user_id]["name"],
                    "file_id": temp_data[user_id]["video"],
                    "duration": temp_data[user_id]["duration"],
                    "size": temp_data[user_id]["size"],
                    "added_by": user_id,
                    "added_at": datetime.now().isoformat()
                }
                save_data(data)
                
                del temp_data[user_id]
                await message.reply_text(
                    f"✅ Film muvaffaqiyatli qo'shildi!\n\n"
                    f"🎬 Kod: `{code}`",
                    parse_mode=enums.ParseMode.MARKDOWN,
                    reply_markup=admin_panel_keyboard()
                )
        
        elif action == "delete_film":
            code = text.strip()
            if code in data["films"]:
                del data["films"][code]
                save_data(data)
                await message.reply_text("✅ Film o'chirildi!", reply_markup=admin_panel_keyboard())
            else:
                await message.reply_text("❌ Bunday kodli film topilmadi!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "add_admin":
            try:
                new_admin = int(text.strip())
                if new_admin in data["admins"]:
                    await message.reply_text("❌ Bu foydalanuvchi allaqachon admin!", reply_markup=admin_panel_keyboard())
                else:
                    data["admins"].append(new_admin)
                    save_data(data)
                    await message.reply_text("✅ Admin qo'shildi!", reply_markup=admin_panel_keyboard())
            except:
                await message.reply_text("❌ Noto'g'ri ID!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "delete_admin":
            try:
                admin_id = int(text.strip())
                if admin_id in data["admins"]:
                    data["admins"].remove(admin_id)
                    save_data(data)
                    await message.reply_text("✅ Admin o'chirildi!", reply_markup=admin_panel_keyboard())
                else:
                    await message.reply_text("❌ Bunday admin topilmadi!", reply_markup=admin_panel_keyboard())
            except:
                await message.reply_text("❌ Noto'g'ri ID!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "add_channel":
            channel = text.strip()
            if channel not in data["channels"]:
                data["channels"].append(channel)
                save_data(data)
                await message.reply_text("✅ Kanal qo'shildi!", reply_markup=admin_panel_keyboard())
            else:
                await message.reply_text("❌ Bu kanal allaqachon qo'shilgan!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "delete_channel":
            channel = text.strip()
            if channel in data["channels"]:
                data["channels"].remove(channel)
                save_data(data)
                await message.reply_text("✅ Kanal o'chirildi!", reply_markup=admin_panel_keyboard())
            else:
                await message.reply_text("❌ Bunday kanal topilmadi!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "set_request":
            channel = text.strip()
            data["request_channel"] = channel
            save_data(data)
            await message.reply_text("✅ Zayafka kanal qo'shildi!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "add_url":
            try:
                name, url = text.split("|")
                name = name.strip()
                url = url.strip()
                data["url_links"].append({"name": name, "url": url})
                save_data(data)
                await message.reply_text("✅ URL link qo'shildi!", reply_markup=admin_panel_keyboard())
            except:
                await message.reply_text("❌ Format: nom | havola", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        elif action == "delete_url":
            name = text.strip()
            data["url_links"] = [l for l in data["url_links"] if l["name"] != name]
            save_data(data)
            await message.reply_text("✅ URL link o'chirildi!", reply_markup=admin_panel_keyboard())
            del temp_data[user_id]
        
        return
    
    if is_admin(user_id):
        if text == "➕ Film qo'shish":
            temp_data[user_id] = {"action": "add_film", "step": "video"}
            await message.reply_text("🎥 Kino videosini yuboring:")
        
        elif text == "🗑 Film o'chirish":
            temp_data[user_id] = {"action": "delete_film"}
            await message.reply_text("🗑 O'chirish uchun film kodini yuboring:")
        
        elif text == "👤 Admin qo'shish":
            temp_data[user_id] = {"action": "add_admin"}
            await message.reply_text("👤 Yangi admin ID raqamini yuboring:")
        
        elif text == "❌ Admin o'chirish":
            temp_data[user_id] = {"action": "delete_admin"}
            await message.reply_text("❌ O'chirish uchun admin ID raqamini yuboring:")
        
        elif text == "📢 Reklama tarqatish":
            temp_data[user_id] = {"action": "broadcast"}
            await message.reply_text("📢 Yuborish uchun xabar, rasm yoki video yuboring:")
        
        elif text == "📺 Majburiy obuna":
            keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("➕ Kanal qo'shish"), KeyboardButton("➖ Kanal o'chirish")],
                [KeyboardButton("🔙 Orqaga")]
            ], resize_keyboard=True)
            
            channels_list = "\n".join([f"• {ch}" for ch in data["channels"]]) if data["channels"] else "Kanallar yo'q"
            await message.reply_text(
                f"📺 Majburiy obuna kanallari:\n\n{channels_list}",
                reply_markup=keyboard
            )
        
        elif text == "➕ Kanal qo'shish":
            temp_data[user_id] = {"action": "add_channel"}
            await message.reply_text("📝 Kanal username yoki ID kiriting:\n\nMasalan: @mykanal yoki -1001234567890")
        
        elif text == "➖ Kanal o'chirish":
            temp_data[user_id] = {"action": "delete_channel"}
            await message.reply_text("📝 O'chirish uchun kanal username yoki ID kiriting:")
        
        elif text == "📨 Zayafka kanal":
            keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("➕ Zayafka qo'shish"), KeyboardButton("➖ Zayafka o'chirish")],
                [KeyboardButton("🔙 Orqaga")]
            ], resize_keyboard=True)
            
            request_text = f"• {data['request_channel']}" if data['request_channel'] else "Zayafka kanal yo'q"
            await message.reply_text(
                f"📨 Zayafka kanali:\n\n{request_text}",
                reply_markup=keyboard
            )
        
        elif text == "➕ Zayafka qo'shish":
            temp_data[user_id] = {"action": "set_request"}
            await message.reply_text("📝 Zayafka kanal username yoki ID kiriting:")
        
        elif text == "➖ Zayafka o'chirish":
            data["request_channel"] = None
            save_data(data)
            await message.reply_text("✅ Zayafka kanal o'chirildi!", reply_markup=admin_panel_keyboard())
        
        elif text == "🔗 URL link":
            keyboard = ReplyKeyboardMarkup([
                [KeyboardButton("➕ URL qo'shish"), KeyboardButton("➖ URL o'chirish")],
                [KeyboardButton("🔙 Orqaga")]
            ], resize_keyboard=True)
            
            links_list = "\n".join([f"• {l['name']}: {l['url']}" for l in data["url_links"]]) if data["url_links"] else "URL linklar yo'q"
            await message.reply_text(
                f"🔗 URL linklar:\n\n{links_list}",
                reply_markup=keyboard
            )
        
        elif text == "➕ URL qo'shish":
            temp_data[user_id] = {"action": "add_url"}
            await message.reply_text("📝 URL link qo'shish:\n\nFormat: nom | havola\n\nMasalan: Instagram | https://instagram.com/mypage")
        
        elif text == "➖ URL o'chirish":
            temp_data[user_id] = {"action": "delete_url"}
            await message.reply_text("📝 O'chirish uchun link nomini kiriting:")
        
        elif text == "📊 Statistika":
            total_users = len(data["users"])
            total_films = len(data["films"])
            total_admins = len(data["admins"]) + 1
            
            await message.reply_text(
                f"📊 **Statistika:**\n\n"
                f"👥 Foydalanuvchilar: {total_users}\n"
                f"🎬 Filmlar: {total_films}\n"
                f"👤 Adminlar: {total_admins}",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        
        elif text == "🔙 Orqaga":
            await message.reply_text("🎛️ Admin panel:", reply_markup=admin_panel_keyboard())
        
        return
    
    code = text.strip()
    if code in data["films"]:
        film = data["films"][code]
        duration_min = film["duration"] // 60
        size_mb = film["size"] / (1024 * 1024)
        
        bot_username = (await client.get_me()).username
        
        caption = (
            f"🎬 **{film['name']}**\n\n"
            f"⏱ Davomiyligi: {duration_min} daqiqa\n"
            f"📦 Hajmi: {size_mb:.1f} MB\n"
            f"🔢 Kodi: `{code}`\n\n"
            f"Bizdan uzoqlashmang, eng so'ngi premyeralar bizda!\n"
            f"@{bot_username}"
        )
        
        await message.reply_video(
            film["file_id"],
            caption=caption,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("❌ Bunday kodli film topilmadi!")

@app.on_message(filters.private & (filters.video | filters.photo))
async def media_handler(client, message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        return
    
    if user_id not in temp_data:
        return
    
    action = temp_data[user_id]["action"]
    
    if action == "add_film" and temp_data[user_id].get("step") == "video":
        if not message.video:
            await message.reply_text("❌ Iltimos, video yuboring!")
            return
        
        temp_data[user_id]["video"] = message.video.file_id
        temp_data[user_id]["duration"] = message.video.duration
        temp_data[user_id]["size"] = message.video.file_size
        temp_data[user_id]["step"] = "name"
        await message.reply_text("📝 Kino nomini kiriting:")
    
    elif action == "broadcast":
        success = 0
        failed = 0
        
        status_msg = await message.reply_text("📤 Reklama yuborilmoqda...")
        
        for uid in data["users"]:
            try:
                if message.text:
                    await client.send_message(uid, message.text)
                elif message.photo:
                    await client.send_photo(uid, message.photo.file_id, caption=message.caption or "")
                elif message.video:
                    await client.send_video(uid, message.video.file_id, caption=message.caption or "")
                success += 1
            except Exception as e:
                failed += 1
            
            if (success + failed) % 20 == 0:
                try:
                    await status_msg.edit_text(
                        f"📤 Yuborilmoqda...\n\n"
                        f"✅ Yuborildi: {success}\n"
                        f"❌ Xato: {failed}"
                    )
                except:
                    pass
            
            await asyncio.sleep(0.05)
        
        try:
            await status_msg.edit_text(
                f"✅ Reklama yuborildi!\n\n"
                f"✅ Muvaffaqiyatli: {success}\n"
                f"❌ Xato: {failed}",
                reply_markup=admin_panel_keyboard()
            )
        except:
            await message.reply_text(
                f"✅ Reklama yuborildi!\n\n"
                f"✅ Muvaffaqiyatli: {success}\n"
                f"❌ Xato: {failed}",
                reply_markup=admin_panel_keyboard()
            )
        
        del temp_data[user_id]

print("🤖 Bot ishga tushdi!")
app.run()
