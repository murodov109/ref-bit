import os
import sqlite3
from datetime import datetime
from ayugram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = set(int(x) for x in os.getenv("ADMINS","").split(",") if x.strip())

app = Client("kino_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY)")
cur.execute("CREATE TABLE IF NOT EXISTS channels(username TEXT PRIMARY KEY, required INTEGER DEFAULT 1, active INTEGER DEFAULT 1)")
cur.execute("CREATE TABLE IF NOT EXISTS links(name TEXT, url TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS requests(name TEXT)")
cur.execute("""CREATE TABLE IF NOT EXISTS movies(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 code TEXT UNIQUE,
 title TEXT,
 file_id TEXT,
 size_bytes INTEGER,
 size_text TEXT,
 duration_seconds INTEGER,
 duration_text TEXT,
 uploaded_by INTEGER,
 uploaded_at TEXT
)""")
conn.commit()
for a in ADMINS:
    cur.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)", (a,))
conn.commit()

states = {}

def fmt_size(n):
    mb = n/1024/1024
    return f"{mb:.0f} MB" if mb<1024 else f"{mb/1024:.2f} GB"

def mk_start_markup():
    rows=[]
    for r in cur.execute("SELECT username FROM channels WHERE active=1"):
        rows.append([InlineKeyboardButton(r[0], url=f"https://t.me/{r[0].lstrip('@')}")])
    if cur.execute("SELECT name,url FROM links").fetchall():
        rows.append([InlineKeyboardButton("🔗 Qo'shimcha havolalar", callback_data="show_links")])
    if cur.execute("SELECT name FROM requests").fetchone():
        rows.append([InlineKeyboardButton("📣 Zayafka", callback_data="show_requests")])
    rows.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_subs")])
    return InlineKeyboardMarkup(rows)

def mk_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Filmlar", callback_data="admin_movies")],
        [InlineKeyboardButton("📡 Kanallar", callback_data="admin_channels"), InlineKeyboardButton("🔗 Havolalar", callback_data="admin_links")],
        [InlineKeyboardButton("👥 Adminlar", callback_data="admin_admins"), InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📣 Zayafka", callback_data="admin_requests"), InlineKeyboardButton("⚙️ Sozlamalar", callback_data="admin_settings")]
    ])

@app.on_message(filters.private & filters.command("start"))
async def start(_, m):
    uid = m.from_user.id
    if cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
        await m.reply("Admin panel", reply_markup=mk_admin_panel())
        return
    await m.reply(f"🎬 Assalomu alaykum, {m.from_user.first_name}!\nIltimos majburiy kanallarga obuna bo‘ling va tasdiqlang.", reply_markup=mk_start_markup())

@app.on_callback_query()
async def cb(_, q):
    uid = q.from_user.id
    data = q.data or ""
    if data=="check_subs":
        missing=[]
        for r in cur.execute("SELECT username FROM channels WHERE active=1 AND required=1"):
            try:
                mem = await app.get_chat_member(r[0], uid)
                if mem.status not in ("member","administrator","creator"):
                    missing.append(r[0])
            except:
                missing.append(r[0])
        if missing:
            await q.message.edit("Quyidagi kanallarga obuna bo‘lishingiz kerak:\n"+ "\n".join(missing), reply_markup=mk_start_markup())
        else:
            await q.message.edit("🎉 Siz barcha majburiy kanallarga obuna bo'lgansiz. Endi kino kodini yuboring.")
        await q.answer()
        return
    if data=="show_links":
        rows = cur.execute("SELECT name,url FROM links").fetchall()
        txt="\n".join(f"{r[0]} — {r[1]}" for r in rows) if rows else "Havola mavjud emas"
        await q.message.reply(txt)
        await q.answer()
        return
    if data=="show_requests":
        rows = cur.execute("SELECT name FROM requests").fetchall()
        txt="\n".join(r[0] for r in rows) if rows else "Zayafka yo'q"
        await q.message.reply(txt)
        await q.answer()
        return
    if data.startswith("admin_"):
        if not cur.execute("SELECT 1 FROM admins WHERE id=?",(uid,)).fetchone():
            await q.answer("Access denied", show_alert=True)
            return
        key=data.split("admin_",1)[1]
        if key=="movies":
            kb=[[InlineKeyboardButton("➕ Yangi film", callback_data="add_movie")],[InlineKeyboardButton("📜 Filmlar ro'yxati", callback_data="list_movies")]]
            await q.message.edit("Filmlar", reply_markup=InlineKeyboardMarkup(kb))
            return
        if key=="channels":
            kb=[[InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],[InlineKeyboardButton("📜 Kanallar", callback_data="list_channels")]]
            await q.message.edit("Kanallar", reply_markup=InlineKeyboardMarkup(kb))
            return
        if key=="links":
            kb=[[InlineKeyboardButton("➕ Havola qo'shish", callback_data="add_link")],[InlineKeyboardButton("📜 Havolalar", callback_data="list_links")]]
            await q.message.edit("Havolalar", reply_markup=InlineKeyboardMarkup(kb))
            return
        if key=="admins":
            kb=[[InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")],[InlineKeyboardButton("📜 Adminlar", callback_data="list_admins")]]
            await q.message.edit("Adminlar", reply_markup=InlineKeyboardMarkup(kb))
            return
        if key=="requests":
            kb=[[InlineKeyboardButton("➕ Zayafka qo'shish", callback_data="add_request")],[InlineKeyboardButton("📜 Zayafkalar", callback_data="list_requests")]]
            await q.message.edit("Zayafka", reply_markup=InlineKeyboardMarkup(kb))
            return
        if key=="stats":
            cnt=cur.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
            await q.message.edit(f"Filmlar soni: {cnt}", reply_markup=mk_admin_panel())
            return
    if data=="add_movie":
        states[uid]={"step":"code"}
        await q.message.reply("1) Kino kodini yuboring")
        return
    if data=="list_movies":
        rows=cur.execute("SELECT code,title,uploaded_at FROM movies ORDER BY id DESC").fetchall()
        txt="\n".join(f"{r[0]} — {r[1]} — {r[2]}" for r in rows) if rows else "Film yo'q"
        await q.message.reply(txt)
        return
    if data.startswith("download_"):
        mid=int(data.split("_",1)[1])
        row=cur.execute("SELECT file_id FROM movies WHERE id=?",(mid,)).fetchone()
        if row: await q.message.reply_video(row[0])
        await q.answer()
        return

@app.on_message(filters.private & filters.text & ~filters.regex(r'^/'))
async def text_handler(_, m):
    uid=m.from_user.id
    txt=m.text.strip()
    if uid in states:
        s=states[uid]
        step=s.get("step")
        if step=="code":
            s["code"]=txt
            s["step"]="title"
            await m.reply("2) Kino nomini yuboring")
            return
        if step=="title":
            s["title"]=txt
            s["step"]="video"
            await m.reply("3) Endi video faylini yuboring (video yoki document)")
            return
    row=cur.execute("SELECT id,code,title,size_text,duration_text FROM movies WHERE code=?",(txt,)).fetchone()
    if row:
        mid,code,title,size_text,duration_text=row
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Yuklab olish", callback_data=f"download_{mid}")],[InlineKeyboardButton("🎬 Boshqa premyeralar", url="https://t.me/")]])
        await m.reply(f"🎞️ {title}\n💾 Hajmi: {size_text}\n⏱ Davomiylik: {duration_text}", reply_markup=kb)
        return
    await m.reply("Kod topilmadi")

@app.on_message(filters.private & (filters.video | filters.document))
async def media_handler(_, m):
    uid=m.from_user.id
    if uid not in states or states[uid].get("step")!="video": return
    s=states[uid]
    file=m.video or m.document
    file_id=file.file_id
    size=getattr(file,"file_size",0)
    dur=getattr(file,"duration",0) or 0
    size_text=fmt_size(size)
    h=dur//3600
    mnt=(dur%3600)//60
    sec=dur%60
    duration_text=f"{h}:{mnt:02d}:{sec:02d}" if h else f"{mnt}:{sec:02d}"
    code=s.get("code")
    title=s.get("title")
    now=datetime.utcnow().isoformat()
    cur.execute("INSERT OR REPLACE INTO movies(code,title,file_id,size_bytes,size_text,duration_seconds,duration_text,uploaded_by,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (code,title,file_id,size,size_text,dur,duration_text,uid,now))
    conn.commit()
    states.pop(uid)
    await m.reply(f"✅ Kino yuklandi\n{title}\n{code}\n{size_text}\n{duration_text}")

if __name__=="__main__":
    print("Bot ishga tushdi")
    app.run()
