import os
import sqlite3
from decimal import Decimal
from dotenv import load_dotenv
from telebot import TeleBot, types

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID","")
BOT_USERNAME = os.getenv("BOT_USERNAME","your_bot_username")
MIN_WITHDRAW = int(os.getenv("MIN_WITHDRAW","10000"))

bot = TeleBot(TOKEN, parse_mode="HTML")
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0, referrals INTEGER DEFAULT 0, ref_by INTEGER DEFAULT 0, active INTEGER DEFAULT 1, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS withdraws(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, dest TEXT, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cur.execute("CREATE TABLE IF NOT EXISTS forced_channels(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT)")
conn.commit()

def get_user(uid):
    r = cur.execute("SELECT id,username,balance,referrals,ref_by FROM users WHERE id=?", (uid,)).fetchone()
    return r

def ensure_user(uid, username, ref_by=0):
    if not cur.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        cur.execute("INSERT INTO users(id,username,balance,ref_by) VALUES(?,?,?,?)", (uid, username or "", 0, ref_by))
        conn.commit()
        if ref_by and cur.execute("SELECT 1 FROM users WHERE id=?", (ref_by,)).fetchone():
            cur.execute("UPDATE users SET referrals = referrals + 1 WHERE id=?", (ref_by,))
            cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (100, ref_by))
            conn.commit()

def make_main_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Hisobim", callback_data="account"))
    kb.add(types.InlineKeyboardButton("Pul ishlash", callback_data="earn"))
    kb.add(types.InlineKeyboardButton("Pul yechish", callback_data="withdraw"))
    kb.add(types.InlineKeyboardButton("Pul yechish so'rovlari", callback_data="my_withdraws"))
    kb.add(types.InlineKeyboardButton("Admin bilan aloqa", callback_data="contact_admin"))
    kb.add(types.InlineKeyboardButton("Isbotlar", callback_data="proofs"))
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
        return st[:1] + "*"*(len(st)-2) + st[-1]
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
    if not ok:
        txt = "Iltimos kanalga obuna bo'ling, so'ng botdan foydalanishingiz mumkin. Kanal: " + str(need)
        bot.send_message(m.chat.id, txt)
        return
    txt = "Xush kelibsiz. Quyidagi tugmalardan birini tanlang."
    bot.send_message(m.chat.id, txt, reply_markup=make_main_kb())

@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    uid = c.from_user.id
    data = c.data
    if data == "account":
        u = get_user(uid)
        bal = u[2] if u else 0
        refcount = u[3] if u else 0
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        txt = f"Hisobingiz: {bal} so'm\nTakliflar: {refcount}\nSizning referal havolangiz:\n{ref_link}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Orqaga", callback_data="back"))
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb)
    elif data == "earn":
        ok, need = check_forced_subscription(uid)
        if not ok:
            bot.answer_callback_query(c.id, "Iltimos majburiy kanalga obuna bo'ling", show_alert=True)
            return
        u = get_user(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        txt = f"Hamkorlik orqali pul ishlang. Har bir yangi foydalanuvchi uchun sizga bonus beriladi.\nSizning havolangiz:\n{ref_link}"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Kopirolish", switch_inline_query_current_chat=ref_link))
        kb.add(types.InlineKeyboardButton("Orqaga", callback_data="back"))
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb)
    elif data == "withdraw":
        bot.send_message(uid, "Iltimos yechmoqchi bo'lgan summangizni yuboring. Minimal: " + str(MIN_WITHDRAW))
    elif data == "my_withdraws":
        rows = cur.execute("SELECT id,amount,status,created_at FROM withdraws WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
        if not rows:
            bot.answer_callback_query(c.id, "Yuborilgan so'rovlar topilmadi", show_alert=True)
            return
        txt = "Sizning so'rovlari:\n"
        for r in rows:
            txt += f"ID:{r[0]} Summa:{r[1]} Holat:{r[2]} Vaqt:{r[3]}\n"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Orqaga", callback_data="back"))
        bot.edit_message_text(txt, c.message.chat.id, c.message.message_id, reply_markup=kb)
    elif data == "contact_admin":
        bot.send_message(uid, "Xabar matnini yuboring, adminga to'g'ridan-to'g'ri yuboraman")
        bot.register_next_step_handler_by_chat_id(uid, forward_to_admin)
    elif data == "proofs":
        url = os.getenv("PROOFS_URL","https://t.me/your_proof_channel")
        bot.send_message(uid, "Isbotlar uchun kanal: " + url)
    elif data == "back":
        bot.edit_message_text("Asosiy menyu", c.message.chat.id, c.message.message_id, reply_markup=make_main_kb())
    else:
        if data.startswith("approve_") or data.startswith("reject_"):
            parts = data.split("_")
            action = parts[0]
            wid = int(parts[1])
            if c.from_user.id not in ADMIN_IDS:
                bot.answer_callback_query(c.id, "Faqat admin", show_alert=True)
                return
            w = cur.execute("SELECT user_id,amount,dest,status FROM withdraws WHERE id=?", (wid,)).fetchone()
            if not w:
                bot.answer_callback_query(c.id, "So'rov topilmadi", show_alert=True)
                return
            if action == "approve":
                cur.execute("UPDATE withdraws SET status='approved' WHERE id=?", (wid,))
                conn.commit()
                masked = mask_sensitive(w[2])
                if CHANNEL_ID:
                    bot.send_message(CHANNEL_ID, f"Yangi pul yechish tasdiqlandi.\nID:{wid}\nFoydalanuvchi: @{bot.get_chat(w[0]).username if bot.get_chat(w[0]) else w[0]}\nSumma: {w[1]}\nManzil: {masked}\nHolat: Tasdiqlandi")
                bot.send_message(w[0], f"Sizning yechish so'rovingiz №{wid} tasdiqlandi. {w[1]} so'm admin tomonidan o'tkazildi.")
                bot.answer_callback_query(c.id, "Tasdiqlandi")
            else:
                cur.execute("UPDATE withdraws SET status='rejected' WHERE id=?", (wid,))
                conn.commit()
                cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (w[1], w[0]))
                conn.commit()
                bot.send_message(w[0], f"Sizning yechish so'rovingiz №{wid} rad etildi. Summa hisobingizga qaytarildi.")
                bot.answer_callback_query(c.id, "Rad etildi")
        elif data.startswith("admin_stats"):
            if c.from_user.id not in ADMIN_IDS:
                bot.answer_callback_query(c.id, "Faqat admin", show_alert=True)
                return
            total = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active = cur.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
            today_new = cur.execute("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')").fetchone()[0]
            total_refs = cur.execute("SELECT SUM(referrals) FROM users").fetchone()[0] or 0
            txt = f"Umumiy foydalanuvchilar: {total}\nAktiv: {active}\nBugungi yangi: {today_new}\nUmumiy takliflar: {total_refs}"
            bot.answer_callback_query(c.id, txt, show_alert=True)

@bot.message_handler(func=lambda m: True, content_types=["text"])
def all_text(m):
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
    if m.chat.type == "private" and m.from_user.id in ADMIN_IDS and text.startswith("/admin"):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Statistika", callback_data="admin_stats"))
        kb.add(types.InlineKeyboardButton("Pul yechish so'rovlari", callback_data="admin_withdraws"))
        kb.add(types.InlineKeyboardButton("Reklama yuborish", callback_data="admin_broadcast"))
        kb.add(types.InlineKeyboardButton("Kanal boshqaruv", callback_data="admin_channels"))
        bot.send_message(uid, "Admin panel", reply_markup=kb)
        return
    bot.send_message(uid, "Asosiy menyu", reply_markup=make_main_kb())

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
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Tasdiqlash", callback_data=f"approve_{wid}"))
    kb.add(types.InlineKeyboardButton("Bekor qilish", callback_data=f"reject_{wid}"))
    for adm in ADMIN_IDS:
        try:
            bot.send_message(adm, f"Yangi pul yechish so'rovi\nID:{wid}\nFoydalanuvchi:{msg.from_user.username or uid}\nSumma:{amount}\nManzil:{dest}", reply_markup=kb)
        except:
            pass
    bot.send_message(uid, "So'rovingiz adminlarga yuborildi. Natijani kuting.")

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
