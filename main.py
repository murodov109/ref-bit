import os
import sqlite3
from dotenv import load_dotenv
from telebot import TeleBot, types

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID","")
BOT_USERNAME = os.getenv("BOT_USERNAME","your_bot_username")

bot = TeleBot(TOKEN, parse_mode="HTML")
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, referrals INTEGER DEFAULT 0, ref_by INTEGER DEFAULT 0, ref_counted INTEGER DEFAULT 0, active INTEGER DEFAULT 1, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS withdraws(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, dest TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS forced_channels(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
conn.commit()

def get_setting(key, default):
    r = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if r:
        try:
            return int(r[0])
        except:
            return r[0]
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(default)))
    conn.commit()
    return default

REF_BONUS = get_setting("ref_bonus", 100)
MIN_WITHDRAW = get_setting("min_withdraw", 10000)

def set_setting(key, value):
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    conn.commit()
    global REF_BONUS, MIN_WITHDRAW
    REF_BONUS = get_setting("ref_bonus", 100)
    MIN_WITHDRAW = get_setting("min_withdraw", 10000)

def get_user(uid):
    r = cur.execute("SELECT id,username,balance,referrals,ref_by,ref_counted FROM users WHERE id=?", (uid,)).fetchone()
    return r

def ensure_user(uid, username, ref_by=0):
    if not cur.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        cur.execute("INSERT INTO users(id,username,balance,ref_by,ref_counted) VALUES(?,?,?,?,?)", (uid, username or "", 0, ref_by or 0, 0))
        conn.commit()
    else:
        cur.execute("UPDATE users SET username=? WHERE id=?", (username or "", uid))
        conn.commit()
    if ref_by:
        credited = cur.execute("SELECT ref_counted FROM users WHERE id=?", (uid,)).fetchone()[0]
        if not credited:
            ok, _ = check_forced_subscription(uid)
            if ok:
                credit_referral(ref_by, uid)

def credit_referral(ref_by, new_user_id):
    if not ref_by:
        return
    if not cur.execute("SELECT 1 FROM users WHERE id=?", (ref_by,)).fetchone():
        return
    cur.execute("UPDATE users SET referrals = referrals + 1 WHERE id=?", (ref_by,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (REF_BONUS, ref_by))
    cur.execute("UPDATE users SET ref_counted=1 WHERE id=?", (new_user_id,))
    conn.commit()
    try:
        bot.send_message(ref_by, f"Taklifingiz tasdiqlandi va sizga {REF_BONUS} so'm berildi")
    except:
        pass

def make_reply_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("👤 Hisobim", "💰 Pul ishlash")
    kb.row("🏦 Pul yechish", "📤 Pul yechish so'rovlari")
    kb.row("📩 Admin bilan aloqa", "📜 Isbotlar")
    return kb

def check_forced_subscription(uid):
    rows = cur.execute("SELECT chat_id FROM forced_channels").fetchall()
    for r in rows:
        chat = r[0]
        try:
            member = bot.get_chat_member(chat, uid)
            if member.status in ["left","kicked"]:
                return False, chat
        except:
            return False, chat
    return True, None

def mask_sensitive(s):
    st = str(s)
    if len(st) <= 6:
        return st[:1] + "*"*(max(0,len(st)-2)) + st[-1:]
    keep_start = 4
    keep_end = 2
    return st[:keep_start] + "*"*(len(st)-keep_start-keep_end) + st[-keep_end:]

@bot.message_handler(commands=["start"])
def start(m):
    args = m.text.split()
    ref_by = 0
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            ref_by = int(args[1].split("_")[1])
        except:
            ref_by = 0
    ensure_user(m.from_user.id, m.from_user.username, ref_by)
    ok, need = check_forced_subscription(m.from_user.id)
    name = m.from_user.first_name or m.from_user.username or "Foydalanuvchi"
    greeting = f"Salom {name}! Botga xush kelibsiz"
    if not ok:
        greeting += f"\nIltimos kanalga obuna bo'ling: {need}"
    bot.send_message(m.chat.id, greeting, reply_markup=make_reply_kb())

@bot.message_handler(func=lambda m: m.text == "👤 Hisobim")
def my_account(m):
    uid = m.from_user.id
    ensure_user(uid, m.from_user.username)
    u = get_user(uid)
    bal = u[2] if u else 0
    refcount = u[3] if u else 0
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    ok, need = check_forced_subscription(uid)
    if not ok:
        bot.send_message(uid, f"Iltimos quyidagi kanalga a'zo bo'ling: {need}")
        return
    cur.execute("SELECT ref_by FROM users WHERE id=?", (uid,))
    ref_by = cur.fetchone()[0] if cur.fetchone() is not None else None
    pending = ""
    if ref_by and not u[5]:
        credit_referral(ref_by, uid)
        pending = "\nSizning referal holating tekshirildi"
    text = f"Hisobingiz: {bal} so'm\nTakliflar: {refcount}\nSizning referal havolangiz:\n{ref_link}{pending}"
    bot.send_message(uid, text)

@bot.message_handler(func=lambda m: m.text == "💰 Pul ishlash")
def earn(m):
    uid = m.from_user.id
    ensure_user(uid, m.from_user.username)
    ok, need = check_forced_subscription(uid)
    if not ok:
        bot.send_message(uid, f"Iltimos majburiy kanalga a'zo bo'ling: {need}")
        return
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    text = f"Hamkorlik orqali pul ishlang. Har bir yangi foydalanuvchi uchun bonus: {REF_BONUS} so'm\nSizning havolangiz:\n{ref_link}"
    bot.send_message(uid, text)

@bot.message_handler(func=lambda m: m.text == "🏦 Pul yechish")
def withdraw_menu(m):
    uid = m.from_user.id
    bot.send_message(uid, f"Iltimos yechmoqchi bo'lgan summangizni yuboring. Minimal: {MIN_WITHDRAW}")

@bot.message_handler(func=lambda m: m.text == "📤 Pul yechish so'rovlari")
def my_withdraws(m):
    uid = m.from_user.id
    rows = cur.execute("SELECT id,amount,status,created_at FROM withdraws WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
    if not rows:
        bot.send_message(uid, "Yuborilgan so'rovlar topilmadi")
        return
    txt = "Sizning so'rovlari:\n"
    for r in rows:
        txt += f"ID:{r[0]} Summa:{r[1]} Holat:{r[2]} Vaqt:{r[3]}\n"
    bot.send_message(uid, txt)

@bot.message_handler(func=lambda m: m.text == "📩 Admin bilan aloqa")
def contact_admin_btn(m):
    uid = m.from_user.id
    bot.send_message(uid, "Xabar matnini yuboring, adminga to'g'ridan-to'g'ri yuboraman")
    bot.register_next_step_handler_by_chat_id(uid, forward_to_admin)

@bot.message_handler(func=lambda m: m.text == "📜 Isbotlar")
def proofs_btn(m):
    url = os.getenv("PROOFS_URL","https://t.me/your_proof_channel")
    bot.send_message(m.from_user.id, "Isbotlar uchun kanal: " + url)

@bot.message_handler(func=lambda m: m.chat.type=="private", content_types=["text"])
def handle_text(m):
    uid = m.from_user.id
    text = m.text.strip()
    if text.isdigit():
        amt = int(text)
        if amt >= MIN_WITHDRAW:
            u = get_user(uid)
            bal = u[2] if u else 0
            if bal < amt:
                bot.send_message(uid, "Hisobingizda yetarli mablag' yo'q")
                return
            bot.send_message(uid, "Iltimos kartangiz yoki telefon raqamingizni yuboring")
            bot.register_next_step_handler_by_chat_id(uid, lambda msg, a=amt: receive_withdraw_dest(msg, a))
            return
    if uid in ADMIN_IDS and text.startswith("/admin"):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("📊 Statistika", "🔧 Sozlamalar")
        kb.row("📥 Pul yechish so'rovlari", "📣 Reklama yuborish")
        kb.row("➕ Kanal qo'shish", "➖ Kanal o'chirish")
        kb.row("➕ Balans qo'shish", "⬅️ Orqaga")
        bot.send_message(uid, "Admin panel", reply_markup=kb)
        return
    if text == "🔧 Sozlamalar" and uid in ADMIN_IDS:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(f"💱 Referal bonusi: {REF_BONUS}", f"💸 Minimal yechish: {MIN_WITHDRAW}")
        kb.row("⬅️ Orqaga")
        bot.send_message(uid, "Sozlamalarni tanlang", reply_markup=kb)
        return
    if text.startswith("💱 Referal bonusi") and uid in ADMIN_IDS:
        bot.send_message(uid, "Yangi referal bonusini summada yuboring")
        bot.register_next_step_handler_by_chat_id(uid, set_ref_bonus)
        return
    if text.startswith("💸 Minimal yechish") and uid in ADMIN_IDS:
        bot.send_message(uid, "Yangi minimal yechish summasini yuboring")
        bot.register_next_step_handler_by_chat_id(uid, set_min_withdraw)
        return
    if text == "📊 Statistika" and uid in ADMIN_IDS:
        total = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active = cur.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        today_new = cur.execute("SELECT COUNT(*) FROM users WHERE date(joined_at)=date('now')").fetchone()[0]
        total_refs = cur.execute("SELECT SUM(referrals) FROM users").fetchone()[0] or 0
        txt = f"Umumiy foydalanuvchilar: {total}\nAktiv: {active}\nBugungi yangi: {today_new}\nUmumiy takliflar: {total_refs}"
        bot.send_message(uid, txt)
        return
    if text == "📥 Pul yechish so'rovlari" and uid in ADMIN_IDS:
        rows = cur.execute("SELECT id,user_id,amount,dest,status,created_at FROM withdraws ORDER BY created_at DESC").fetchall()
        txt = ""
        for r in rows:
            txt += f"ID:{r[0]} User:{r[1]} Sum:{r[2]} Manzil:{mask_sensitive(r[3])} Holat:{r[4]}\n"
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        bot.send_message(uid, "Hamma so'rovlar:\n" + txt)
        return
    if text == "➕ Kanal qo'shish" and uid in ADMIN_IDS:
        bot.send_message(uid, "Kanal usernameni yoki id ni yuboring")
        bot.register_next_step_handler_by_chat_id(uid, add_channel)
        return
    if text == "➖ Kanal o'chirish" and uid in ADMIN_IDS:
        bot.send_message(uid, "O'chirmoqchi bo'lgan kanal usernameni yoki id ni yuboring")
        bot.register_next_step_handler_by_chat_id(uid, remove_channel)
        return
    if text == "➕ Balans qo'shish" and uid in ADMIN_IDS:
        bot.send_message(uid, "Foydalanuvchi id va summa: user_id summa")
        bot.register_next_step_handler_by_chat_id(uid, admin_add_balance)
        return
    if text == "📣 Reklama yuborish" and uid in ADMIN_IDS:
        bot.send_message(uid, "Reklama matnini yuboring")
        bot.register_next_step_handler_by_chat_id(uid, admin_broadcast)
        return
    if text == "⬅️ Orqaga":
        bot.send_message(uid, "Asosiy menyu", reply_markup=make_reply_kb())
        return
    bot.send_message(uid, "Asosiy menyu", reply_markup=make_reply_kb())

def set_ref_bonus(m):
    uid = m.from_user.id
    try:
        v = int(m.text.strip())
        set_setting("ref_bonus", v)
        bot.send_message(uid, f"Referal bonusi o'zgartirildi: {v}")
    except:
        bot.send_message(uid, "Iltimos son kiriting")

def set_min_withdraw(m):
    uid = m.from_user.id
    try:
        v = int(m.text.strip())
        set_setting("min_withdraw", v)
        bot.send_message(uid, f"Minimal yechish summa o'zgardi: {v}")
    except:
        bot.send_message(uid, "Iltimos son kiriting")

def add_channel(m):
    uid = m.from_user.id
    chat = m.text.strip()
    cur.execute("INSERT INTO forced_channels(chat_id) VALUES(?)", (chat,))
    conn.commit()
    bot.send_message(uid, "Kanal qo'shildi")

def remove_channel(m):
    uid = m.from_user.id
    chat = m.text.strip()
    cur.execute("DELETE FROM forced_channels WHERE chat_id=?", (chat,))
    conn.commit()
    bot.send_message(uid, "Kanal o'chirildi")

def admin_add_balance(m):
    uid = m.from_user.id
    parts = m.text.strip().split()
    try:
        user_id = int(parts[0])
        amt = int(parts[1])
        cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amt, user_id))
        conn.commit()
        bot.send_message(uid, "Balans yuklandi")
        try:
            bot.send_message(user_id, f"Hisobingizga {amt} so'm qo'shildi. Admin tomonidan")
        except:
            pass
    except:
        bot.send_message(uid, "Format xato. user_id summa")

def admin_broadcast(m):
    uid = m.from_user.id
    text = m.text
    rows = cur.execute("SELECT id FROM users").fetchall()
    for r in rows:
        try:
            bot.send_message(r[0], text)
        except:
            pass
    bot.send_message(uid, "Xabar tarqatildi")

def receive_withdraw_dest(msg, amount):
    uid = msg.from_user.id
    dest = msg.text.strip()
    u = get_user(uid)
    if not u:
        bot.send_message(uid, "Foydalanuvchi topilmadi")
        return
    if u[2] < amount:
        bot.send_message(uid, "Hisobingizda yetarli mablag' yo'q")
        return
    cur.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, uid))
    cur.execute("INSERT INTO withdraws(user_id,amount,dest,status) VALUES(?,?,?,?)", (uid, amount, dest, "pending"))
    conn.commit()
    wid = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    kb_text = f"Tasdiqlash_{wid}"
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(f"✅ Tasdiqlash {wid}", f"❌ Rad etish {wid}")
    for adm in ADMIN_IDS:
        try:
            bot.send_message(adm, f"Yangi pul yechish so'rovi\nID:{wid}\nFoydalanuvchi:{msg.from_user.username or uid}\nSumma:{amount}\nManzil:{dest}", reply_markup=kb)
        except:
            pass
    bot.send_message(uid, "So'rovingiz adminlarga yuborildi. Natijani kuting.")

@bot.message_handler(func=lambda m: m.text and m.from_user.id in ADMIN_IDS)
def admin_action_handler(m):
    text = m.text.strip()
    if text.startswith("✅ Tasdiqlash"):
        try:
            wid = int(text.split()[-1])
            w = cur.execute("SELECT user_id,amount,dest,status FROM withdraws WHERE id=?", (wid,)).fetchone()
            if not w or w[3] != "pending":
                bot.send_message(m.from_user.id, "So'rov topilmadi yoki holati o'zgargan")
                return
            cur.execute("UPDATE withdraws SET status='approved' WHERE id=?", (wid,))
            conn.commit()
            masked = mask_sensitive(w[2])
            if CHANNEL_ID:
                bot.send_message(CHANNEL_ID, f"Yangi pul yechish tasdiqlandi.\nID:{wid}\nFoydalanuvchi: {w[0]}\nSumma: {w[1]}\nManzil: {masked}\nHolat: Tasdiqlandi")
            bot.send_message(w[0], f"Sizning yechish so'rovingiz №{wid} tasdiqlandi. {w[1]} so'm admin tomonidan o'tkazildi.")
            bot.send_message(m.from_user.id, "Tasdiqlandi")
        except:
            bot.send_message(m.from_user.id, "Xato format")
    if text.startswith("❌ Rad etish"):
        try:
            wid = int(text.split()[-1])
            w = cur.execute("SELECT user_id,amount,dest,status FROM withdraws WHERE id=?", (wid,)).fetchone()
            if not w or w[3] != "pending":
                bot.send_message(m.from_user.id, "So'rov topilmadi yoki holati o'zgargan")
                return
            cur.execute("UPDATE withdraws SET status='rejected' WHERE id=?", (wid,))
            conn.commit()
            cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (w[1], w[0]))
            conn.commit()
            bot.send_message(w[0], f"Sizning yechish so'rovingiz №{wid} rad etildi. Summa hisobingizga qaytarildi.")
            bot.send_message(m.from_user.id, "Rad etildi va summa qaytarildi")
        except:
            bot.send_message(m.from_user.id, "Xato format")

def forward_to_admin(message):
    for adm in ADMIN_IDS:
        try:
            bot.send_message(adm, f"Foydalanuvchidan xabar:\nFrom: @{message.from_user.username or message.from_user.id}\n{message.text}")
        except:
            pass
    bot.send_message(message.chat.id, "Xabaringiz adminlarga yuborildi")

def run_polling():
    bot.infinity_polling()

if __name__ == "__main__":
    run_polling()
