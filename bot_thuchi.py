#!/usr/bin/env python3
import sqlite3
import re
from datetime import datetime, timedelta, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Updater, CommandHandler, CallbackQueryHandler,
                          CallbackContext, JobQueue)

CHAT_ID = 6171342264

conn = sqlite3.connect('thu_chi.db', check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS giao_dich (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    amount INTEGER,
    note TEXT,
    date TEXT)""")
conn.commit()

def parse_amount(amount_str: str) -> int:
    amount_str = amount_str.lower().replace(",", "").strip()
    if amount_str.endswith("k"):
        return int(float(amount_str[:-1]))
    elif "tr" in amount_str:
        match = re.match(r"(\d+(?:\.\d+)?)(tr)?(\d+)?", amount_str)
        if match:
            millions = float(match.group(1))
            thousands = int(match.group(3)) if match.group(3) else 0
            return int(millions * 1000 + thousands)
    return int(amount_str)

def format_amount(amount: int) -> str:
    if amount >= 1000 and amount % 1000 == 0:
        return f"{amount // 1000} triệu VND"
    return f"{amount} nghìn VND"

def add_transaction(update: Update, context: CallbackContext, type_: str):
    try:
        amount = parse_amount(context.args[0])
        note = ' '.join(context.args[1:])
        now = datetime.now().strftime("%Y-%m-%d")
        cur.execute("INSERT INTO giao_dich (type, amount, note, date) VALUES (?, ?, ?, ?)",
                    (type_, amount, note, now))
        conn.commit()
        update.message.reply_text(f"✅ Đã ghi {type_}: {format_amount(amount)} ({note})")
        check_auto_summary(update)
    except:
        update.message.reply_text("❌ Sai cú pháp. Dùng: /thu 200k ăn sáng")

def check_auto_summary(update: Update):
    cur.execute("SELECT MIN(date), MAX(date) FROM giao_dich")
    min_date, max_date = cur.fetchone()
    if min_date and max_date:
        fmt = "%Y-%m-%d"
        diff = (datetime.strptime(max_date, fmt) - datetime.strptime(min_date, fmt)).days + 1
        if diff % 30 == 0:
            update.message.reply_text(tong_thang_text())
        elif diff % 7 == 0:
            update.message.reply_text(tong_tuan_text())

def thu(update: Update, context: CallbackContext):
    add_transaction(update, context, 'thu')

def chi(update: Update, context: CallbackContext):
    add_transaction(update, context, 'chi')

def hoantac(update: Update, context: CallbackContext):
    cur.execute("SELECT id, type, amount, note FROM giao_dich ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM giao_dich WHERE id = ?", (row[0],))
        conn.commit()
        update.message.reply_text(f"↩️ Đã hoàn tác: {row[1]} {format_amount(row[2])} ({row[3]})")
    else:
        update.message.reply_text("❌ Không có giao dịch nào để hoàn tác.")

def tukhoa(update: Update, context: CallbackContext):
    keyword = ' '.join(context.args).strip()
    cur.execute("SELECT date, type, amount, note FROM giao_dich WHERE note LIKE ?", (f"%{keyword}%",))
    rows = cur.fetchall()
    if not rows:
        update.message.reply_text("❌ Không tìm thấy.")
        return
    text = ""
    thu = chi = 0
    for date, type_, amount, note in rows:
        text += f"{date} {'+' if type_ == 'thu' else '-'}{amount}k ({note})\n"
        thu += amount if type_ == 'thu' else 0
        chi += amount if type_ == 'chi' else 0
    text += f"\nTổng thu: {thu}k\nTổng chi: {chi}k\nSố dư: {thu - chi}k"
    update.message.reply_text(text)

def xoa(update: Update, context: CallbackContext):
    if context.args and context.args[0] == 'all':
        cur.execute("DELETE FROM giao_dich")
        conn.commit()
        update.message.reply_text("🗑️ Đã xoá toàn bộ dữ liệu thu chi.")
    elif re.match(r"\d{4}-\d{2}-\d{2}", context.args[0]):
        cur.execute("DELETE FROM giao_dich WHERE date = ?", (context.args[0],))
        conn.commit()
        update.message.reply_text(f"🗑️ Đã xoá dữ liệu ngày {context.args[0]}")
    elif re.match(r"\d{4}-\d{2}", context.args[0]):
        cur.execute("DELETE FROM giao_dich WHERE substr(date, 1, 7) = ?", (context.args[0],))
        conn.commit()
        update.message.reply_text(f"🗑️ Đã xoá dữ liệu tháng {context.args[0]}")
    else:
        update.message.reply_text("❌ Sai cú pháp. Dùng: /xoa YYYY-MM-DD hoặc YYYY-MM hoặc all")

def get_summary(start=None, end=None):
    query = "SELECT type, amount FROM giao_dich"
    params = ()
    if start and end:
        query += " WHERE date BETWEEN ? AND ?"
        params = (start, end)
    cur.execute(query, params)
    rows = cur.fetchall()
    thu = sum(r[1] for r in rows if r[0] == 'thu')
    chi = sum(r[1] for r in rows if r[0] == 'chi')
    return thu, chi, thu - chi

def tong_homnay(update: Update, context: CallbackContext):
    today = datetime.now().strftime('%Y-%m-%d')
    thu, chi, sodu = get_summary(today, today)
    msg = f"📅 Hôm nay:\n+ Thu: {thu}k\n- Chi: {chi}k\n= Số dư: {sodu}k"
    if sodu > 2000:
        msg += "\n🚀 DKM mua nhà mua xe cố lên cố lên"
    elif sodu > 1000:
        msg += "\n👍 DKM 1 tháng 30 củ, cố lên"
    elif sodu > 500:
        msg += "\n💪 DKM cố hơn nữa.. Tiếp tục phát huy nhé!"
    elif sodu < 0:
        msg += "\n⚠️ DKMM ăn chơi ít thôi đụ má mày"
    update.message.reply_text(msg)

def tong_tuan_text():
    today = datetime.now()
    start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    thu, chi, sodu = get_summary(start, end)
    return f"📅 Tuần này:\n+ Thu: {thu}k\n- Chi: {chi}k\n= Số dư: {sodu}k"

def tong_thang_text():
    today = datetime.now()
    start = today.replace(day=1).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')
    thu, chi, sodu = get_summary(start, end)
    return f"📅 Tháng này:\n+ Thu: {thu}k\n- Chi: {chi}k\n= Số dư: {sodu}k"

def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("📅 Tổng hôm nay", callback_data='tong_homnay')],
        [InlineKeyboardButton("📆 Tổng tuần", callback_data='tong_tuan')],
        [InlineKeyboardButton("🗓 Tổng tháng", callback_data='tong_thang')],
        [InlineKeyboardButton("↩️ Hoàn tác", callback_data='hoantac')],
        [InlineKeyboardButton("🔍 Từ khoá", callback_data='tukhoa')],
        [InlineKeyboardButton("🗑 Xoá dữ liệu", callback_data='xoa')],
    ]
    update.message.reply_text('📌 Chọn một hành động:', reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    updater = Updater("8420801096:AAE-Jg1F4ssZF09kLyYkOXWlEo0weYER_t4", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("thu", thu))
    dp.add_handler(CommandHandler("chi", chi))
    dp.add_handler(CommandHandler("hoantac", hoantac))
    dp.add_handler(CommandHandler("tukhoa", tukhoa))
    dp.add_handler(CommandHandler("xoa", xoa))
    dp.add_handler(CommandHandler("tong_homnay", tong_homnay))

    job = updater.job_queue
    job.run_daily(lambda ctx: ctx.bot.send_message(chat_id=CHAT_ID, text="📥 Nhớ ghi thu/chi hôm nay nhé!"),
                  time=time(hour=23, minute=0))
    job.run_daily(lambda ctx: ctx.bot.send_message(chat_id=CHAT_ID, text="💡 Ghi chú hôm nay tích cực không? Keep going 💪"),
                  time=time(hour=23, minute=30))

    updater.start_polling(drop_pending_updates=True)
    print("🤖 Bot đã khởi động thành công...")
    updater.idle()

if __name__ == '__main__':
    main()
