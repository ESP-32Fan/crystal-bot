import os
import random
import sqlite3
from datetime import date
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ['TELEGRAM_TOKEN']

# Если нужен прокси — установи: pip install PySocks
# И раскомментируй строки ниже, вставив свой прокси:
# from telebot import apihelper
# apihelper.proxy = {'https': 'socks5://login:password@proxy_host:port'}

bot = telebot.TeleBot(TOKEN)

# ============================================
# БАЗА ДАННЫХ (оптимизированная)
# ============================================
DB_FILE = 'crystals.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")  # быстрее
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 100,
            total_rolls INTEGER DEFAULT 0,
            last_daily TEXT DEFAULT ''
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collection (
            user_id INTEGER,
            crystal_type TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, crystal_type),
            FOREIGN KEY (user_id) REFERENCES users(telegram_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user is None:
        cursor.execute('INSERT INTO users (telegram_id, balance) VALUES (?, 100)', (user_id,))
        conn.commit()
        user = (user_id, 100, 0, '')
    
    conn.close()
    return {'id': user[0], 'balance': user[1], 'rolls': user[2], 'daily': user[3]}

def update_balance(user_id, amount):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE telegram_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_to_collection(user_id, crystal_type):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT count FROM collection WHERE user_id = ? AND crystal_type = ?', 
                   (user_id, crystal_type))
    result = cursor.fetchone()
    
    if result:
        cursor.execute('UPDATE collection SET count = count + 1 WHERE user_id = ? AND crystal_type = ?', 
                       (user_id, crystal_type))
    else:
        cursor.execute('INSERT INTO collection (user_id, crystal_type, count) VALUES (?, ?, 1)', 
                       (user_id, crystal_type))
    
    conn.commit()
    conn.close()

def get_collection(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT crystal_type, count FROM collection WHERE user_id = ?', (user_id,))
    result = cursor.fetchall()
    conn.close()
    return result

# ============================================
# СИСТЕМА РЕДКОСТЕЙ
# ============================================
CRYSTALS = [
    {'type': 'mythic',    'name': 'Мифический',  'emoji': '⚡', 'color': '🟣', 'chance': 10000, 'price': 1000},
    {'type': 'legendary', 'name': 'Легендарный', 'emoji': '🔥', 'color': '🔴', 'chance': 1000,  'price': 100},
    {'type': 'epic',      'name': 'Эпический',   'emoji': '💜', 'color': '🟠', 'chance': 100,   'price': 50},
    {'type': 'rare',      'name': 'Редкий',      'emoji': '💎', 'color': '🟣', 'chance': 20,    'price': 20},
    {'type': 'uncommon',  'name': 'Необычный',   'emoji': '💚', 'color': '🟢', 'chance': 5,     'price': 10},
    {'type': 'common',    'name': 'Обычный',     'emoji': '🔵', 'color': '⚪', 'chance': 2,     'price': 5},
]

def roll_crystal():
    for crystal in CRYSTALS:
        if random.randint(1, crystal['chance']) == 1:
            return crystal
    return CRYSTALS[-1]

def make_roll_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    roll_btn = types.InlineKeyboardButton('🎲 ROLL (5 🪙)', callback_data='roll')
    keyboard.add(roll_btn)
    return keyboard

# ============================================
# КОМАНДЫ
# ============================================

@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.chat.id)
    text = (
        f"💎 <b>CrystalRoll Bot</b> 💎\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"🎲 Нажми <b>ROLL</b> чтобы получить случайный кристалл\n"
        f"🪙 У тебя <b>{user['balance']}</b> монет\n"
        f"💰 Каждый ролл: +10 монет, цена ролла: 5 монет\n\n"
        f"📋 Команды:\n"
        f"/collection — твоя коллекция\n"
        f"/balance — твой баланс\n"
        f"/daily — ежедневный бонус (+50 монет)\n"
        f"/help — помощь"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=make_roll_keyboard())

@bot.message_handler(commands=['balance'])
def balance(message):
    user = get_user(message.chat.id)
    bot.send_message(message.chat.id, 
        f"💰 Твой баланс: <b>{user['balance']} монет</b>\n"
        f"🎲 Всего роллов: <b>{user['rolls']}</b>",
        parse_mode='HTML')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    text = (
        "📋 <b>Команды:</b>\n\n"
        "/start — приветствие\n"
        "/balance — твой баланс\n"
        "/collection — посмотреть коллекцию\n"
        "/daily — ежедневный бонус (+50 🪙)\n\n"
        "🎲 Нажми кнопку ROLL чтобы бросить кристалл!\n\n"
        "<b>Редкости:</b>\n"
        "⚡ Мифический — 1/10000\n"
        "🔥 Легендарный — 1/1000\n"
        "💜 Эпический — 1/100\n"
        "💎 Редкий — 1/20\n"
        "💚 Необычный — 1/5\n"
        "🔵 Обычный — 1/2"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')

@bot.message_handler(commands=['daily'])
def daily(message):
    user = get_user(message.chat.id)
    today = date.today().isoformat()
    
    if user['daily'] == today:
        bot.send_message(message.chat.id, "🎁 Ты уже получал бонус сегодня! Возвращайся завтра.")
        return
    
    update_balance(message.chat.id, 50)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_daily = ? WHERE telegram_id = ?', (today, message.chat.id))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "🎁 <b>+50 монет!</b> Возвращайся завтра за ещё одним бонусом.", parse_mode='HTML')

@bot.message_handler(commands=['collection'])
def collection(message):
    items = get_collection(message.chat.id)
    
    if not items:
        bot.send_message(message.chat.id, "📦 Твоя коллекция пуста. Нажми ROLL чтобы начать!")
        return
    
    text = "📦 <b>Твоя коллекция:</b>\n\n"
    
    rarity_order = {c['type']: i for i, c in enumerate(CRYSTALS)}
    items_sorted = sorted(items, key=lambda x: rarity_order.get(x[0], 999))
    
    total = 0
    for crystal_type, count in items_sorted:
        crystal = next((c for c in CRYSTALS if c['type'] == crystal_type), None)
        if crystal:
            text += f"{crystal['color']} {crystal['emoji']} <b>{crystal['name']}</b> — x{count}\n"
            total += count
    
    text += f"\n📊 Всего кристаллов: <b>{total}</b>"
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# ============================================
# КНОПКА ROLL
# ============================================

@bot.callback_query_handler(func=lambda call: call.data == 'roll')
def roll_callback(call):
    user = get_user(call.message.chat.id)
    
    if user['balance'] < 5:
        bot.answer_callback_query(call.id, "❌ Не хватает монет! Получи /daily")
        return
    
    update_balance(call.message.chat.id, 5)  # -5 +10 = +5
    
    crystal = roll_crystal()
    add_to_collection(call.message.chat.id, crystal['type'])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET total_rolls = total_rolls + 1 WHERE telegram_id = ?', (call.message.chat.id,))
    conn.commit()
    conn.close()
    
    chance_str = f"1 in {crystal['chance']:,}"
    
    if crystal['chance'] >= 1000:
        result_text = (
            f"🎉 <b>НЕВЕРОЯТНО!</b> 🎉\n\n"
            f"{crystal['emoji']} Тебе выпал <b>{crystal['name']} кристалл</b>!\n"
            f"Шанс: <b>{chance_str}</b>\n\n"
            f"💎 Это огромная удача!"
        )
    elif crystal['chance'] >= 100:
        result_text = (
            f"✨ <b>Отличный дроп!</b>\n\n"
            f"{crystal['emoji']} <b>{crystal['name']} кристалл</b>\n"
            f"Шанс: {chance_str}"
        )
    else:
        result_text = (
            f"{crystal['emoji']} <b>{crystal['name']} кристалл</b>\n"
            f"Шанс: {chance_str}"
        )
    
    bot.edit_message_text(result_text, call.message.chat.id, call.message.id, 
                         parse_mode='HTML', reply_markup=make_roll_keyboard())
    bot.answer_callback_query(call.id)

# ============================================
# ЗАПУСК
# ============================================

if __name__ == '__main__':
    print("🚀 CrystalBot запущен!")
    init_db()
    bot.infinity_polling()
