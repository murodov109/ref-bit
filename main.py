import os
import sqlite3
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMINS = set(int(x) for x in os.getenv("ADMINS","").split(",") if x.strip())

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, required INTEGER, active INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS links(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS movies(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, file_id TEXT, size_bytes INTEGER, size_text TEXT, duration_seconds INTEGER, duration_text TEXT, uploaded_by INTEGER, uploaded_at TEXT)")
conn.commit()

for a in ADMINS:
    cur.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)",(a,))
conn.commit()

admin_state = {}

def mk_admin_panel():
    kb = [
        [InlineKeyboardButton("📁 Filmlar", callback_data="admin_movies")],
        [InlineKeyboardButton("📡 Kanallar", callback_data="admin_channels"), InlineKeyboardButton("🔗 Havolalar", callback_data="admin_links")],
        [InlineKeyboardButton("👥 Adminlar", callback_data="admin_admins"), InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(kb)

def mk_start_markup(user_id):
    rows = []
    cur.execute("SELECT username FROM channels WHERE active=1")
    for r in cur.fetchall():
        rows.append([InlineKeyboardButton(r[0], url=f"https://t.me/{r[0].lstrip('@')}")])
    cur.execute("SELECT name,url FROM links")
    links = cur.fetchall()
    if links:
        rows.append([InlineKeyboardButton("🔗 Qoʻshimcha havolalar", callback_data="show_links")])
    rows.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(rows)

def fmt_size(n):
    mb = n/1024/1024
    if mb<1024:
        return f"{mb:.0f} MB"
    return f"{mb/1024:.2f} GB"

from datetime import datetime
app = Client("kino_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.private & filters.command("start"))
async def start(c, m):
    uid = m.from_user.id
    if cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        await m.reply("Admin panelga xush kelibsiz", reply_markup=mk_admin_panel())
        return
    text = f"🎬 Assalomu alaykum, {m.from_user.first_name}!\nKinolarni olish uchun pastdagi kanallarga obuna bo'ling."
    await m.reply(text, reply_markup=mk_start_markup(uid))

@app.on_callback_query()
async def cb(c, q):
    uid = q.from_user.id
    data = q.data
    if data == "check_subs":
        cur.execute("SELECT username FROM channels WHERE active=1 AND required=1")
        rows = cur.fetchall()
        missing=[]
        for r in rows:
            try:
                status = await app.get_chat_member(r[0], uid)
                if status.status in ("member","creator","administrator"):
                    continue
            except:
                missing.append(r[0])
        if missing:
            txt = "Quyidagi kanallarga obuna bo'lishingiz kerak:\n" + "\n".join(missing)
            await q.answer()
            await q.message.edit(txt, reply_markup=mk_start_markup(uid))
        else:
            await q.answer("Obuna tekshirildi")
            await q.message.edit("Siz barcha majburiy kanallarga obuna bo'lgansiz. Endi kod yuboring.", reply_markup=None)
    elif data == "show_links":
        cur.execute("SELECT name,url FROM links")
        rows = cur.fetchall()
        txt = "🔗 Qoʻshimcha havolalar:\n" + "\n".join(f"{r[0]} — {r[1]}" for r in rows) if rows else "Havolalar mavjud emas"
        await q.answer()
        await q.message.reply(txt)
    elif data.startswith("admin_") and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        key = data.split("_",1)[1]
        if key=="movies":
            kb = [[InlineKeyboardButton("➕ Yangi film", callback_data="add_movie")],[InlineKeyboardButton("📜 Filmlar ro'yxati", callback_data="list_movies")]]
            await q.message.edit("Filmlar boshqaruvi", reply_markup=InlineKeyboardMarkup(kb))
        elif key=="channels":
            kb = [[InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],[InlineKeyboardButton("📜 Kanallar ro'yxati", callback_data="list_channels")]]
            await q.message.edit("Kanallar boshqaruvi", reply_markup=InlineKeyboardMarkup(kb))
        elif key=="links":
            kb = [[InlineKeyboardButton("➕ Havola qo'shish", callback_data="add_link")],[InlineKeyboardButton("📜 Havolalar ro'yxati", callback_data="list_links")]]
            await q.message.edit("Havolalar boshqaruvi", reply_markup=InlineKeyboardMarkup(kb))
        elif key=="admins":
            kb = [[InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],[InlineKeyboardButton("📜 Adminlar ro'yxati", callback_data="list_admins")]]
            await q.message.edit("Adminlar boshqaruvi", reply_markup=InlineKeyboardMarkup(kb))
        elif key=="stats":
            users = await app.get_me()
            await q.answer()
            await q.message.reply("Statistika paneli")
        elif key=="settings":
            await q.message.edit("Sozlamalar", reply_markup=mk_admin_panel())
    elif data == "add_movie" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        admin_state[uid] = {"step":"code"}
        await q.message.reply("1) Kinoga beriladigan kodni yuboring")
    elif data == "list_movies" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        cur.execute("SELECT code,title FROM movies ORDER BY id DESC")
        rows = cur.fetchall()
        txt = "\n".join(f"{r[0]} — {r[1]}" for r in rows) if rows else "Film yo'q"
        await q.message.reply(txt)
    elif data == "add_channel" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        admin_state[uid] = {"step":"channel_username"}
        await q.message.reply("Kanal username (@username) kiriting")
    elif data == "list_channels" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        cur.execute("SELECT username,required,active FROM channels")
        rows = cur.fetchall()
        txt = "\n".join(f"{r[0]} — required={r[1]} active={r[2]}" for r in rows) if rows else "Kanal yo'q"
        await q.message.reply(txt)
    elif data == "add_link" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        admin_state[uid] = {"step":"link_name"}
        await q.message.reply("Havola nomini kiriting (masalan: Instagram)")
    elif data == "list_links" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        cur.execute("SELECT name,url FROM links")
        rows = cur.fetchall()
        txt = "\n".join(f"{r[0]} — {r[1]}" for r in rows) if rows else "Havola yo'q"
        await q.message.reply(txt)
    elif data == "add_admin" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        admin_state[uid] = {"step":"new_admin"}
        await q.message.reply("Qo'shmoqchi bo'lgan adminning Telegram ID sini yuboring")
    elif data == "list_admins" and cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        cur.execute("SELECT id FROM admins")
        rows = cur.fetchall()
        txt = "\n".join(str(r[0]) for r in rows)
        await q.message.reply(txt)
    elif data.startswith("download_"):
        mid = int(data.split("_",1)[1])
        cur.execute("SELECT file_id FROM movies WHERE id=?", (mid,))
        r = cur.fetchone()
        if r:
            await q.message.reply_video(r[0])
        await q.answer()

@app.on_message(filters.private & filters.text & ~filters.command)
async def text_handler(c, m):
    uid = m.from_user.id
    txt = m.text.strip()
    if uid in admin_state:
        s = admin_state[uid]
        if s["step"]=="code":
            s["code"]=txt
            s["step"]="title"
            await m.reply("2) Kino nomini yuboring")
            return
        if s["step"]=="title":
            s["title"]=txt
            s["step"]="video"
            await m.reply("3) Endi video faylini yuboring")
            return
        if s["step"]=="channel_username":
            uname = txt.lstrip("@")
            cur.execute("INSERT OR IGNORE INTO channels(username,required,active) VALUES(?,?,?)",(f"@{uname}",1,1))
            conn.commit()
            admin_state.pop(uid,None)
            await m.reply("Kanal qo'shildi")
            return
        if s["step"]=="link_name":
            s["link_name"]=txt
            s["step"]="link_url"
            await m.reply("Havola URL ni yuboring")
            return
        if s["step"]=="link_url":
            name = s.get("link_name")
            url = txt
            cur.execute("INSERT INTO links(name,url) VALUES(?,?)",(name,url))
            conn.commit()
            admin_state.pop(uid,None)
            await m.reply("Havola qo'shildi")
            return
        if s["step"]=="new_admin":
            try:
                nid = int(txt)
                cur.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)",(nid,))
                conn.commit()
                admin_state.pop(uid,None)
                await m.reply("Admin qo'shildi")
            except:
                await m.reply("ID raqam bo'lishi kerak")
            return
    # foydalanuvchi kod tekshiruvi
    cur.execute("SELECT id,code,title,size_text,duration_text FROM movies WHERE code=?", (txt,))
    r = cur.fetchone()
    if r:
        mid,code,title,size_text,duration_text = r
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Kinoni yuklab olish", callback_data=f"download_{mid}")],[InlineKeyboardButton("🎬 Boshqa premyeralar", url="https://t.me/")]])
        await m.reply(f"🎞️ {title}\n💾 Hajmi: {size_text}\n⏱ Davomiylik: {duration_text}", reply_markup=kb)
        return
    await m.reply("Kod topilmadi")

@app.on_message(filters.video | filters.document)
async def media_handler(c, m):
    uid = m.from_user.id
    if uid in admin_state and admin_state[uid].get("step")=="video":
        s = admin_state[uid]
        file = None
        if m.video:
            file = m.video
        elif m.document:
            file = m.document
        if not file:
            await m.reply("Video topilmadi")
            return
        file_id = file.file_id
        size = getattr(file, "file_size", 0) or 0
        dur = getattr(file, "duration", 0) or 0
        size_text = fmt_size(size)
        h = dur//3600
        mnt = (dur%3600)//60
        sec = dur%60
        duration_text = f"{h}:{mnt:02d}:{sec:02d}" if h else f"{mnt}:{sec:02d}"
        code = s.get("code")
        title = s.get("title")
        now = datetime.utcnow().isoformat()
        cur.execute("INSERT OR REPLACE INTO movies(code,title,file_id,size_bytes,size_text,duration_seconds,duration_text,uploaded_by,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (code,title,file_id,size,size_text,dur,duration_text,uid,now))
        conn.commit()
        admin_state.pop(uid,None)
        await m.reply(f"✅ Kino yuklandi\n{title}\n{code}\n{size_text}\n{duration_text}")
        return

if __name__ == "__main__":
    app.run()
