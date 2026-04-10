import vk_api
import random
import os
import time
import sqlite3
from flask import Flask
from threading import Thread
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# === НАСТРОЙКИ ===
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')

if not VK_TOKEN:
    print("❌ Ошибка: VK_TOKEN не найден!")
    exit(1)

if not GROUP_ID:
    print("❌ Ошибка: GROUP_ID не указан в переменных окружения!")
    print("💡 Добавьте переменную GROUP_ID с ID вашего сообщества")
    exit(1)

GROUP_ID = int(GROUP_ID)
print(f"📋 Токен загружен, GROUP_ID: {GROUP_ID}")

# === ПРОВЕРКА ТОКЕНА ===
try:
    vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.199')
    vk = vk_session.get_api()
    
    # Проверяем токен через groups.getById с явным group_id
    try:
        group_info = vk.groups.getById(group_id=GROUP_ID)
        print(f"✅ Авторизация успешна! Группа: {group_info[0]['name']}")
    except vk_api.exceptions.ApiError as e:
        print(f"❌ Ошибка API: {e}")
        exit(1)
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    exit(1)

# === БАЗА ДАННЫХ ===
conn = sqlite3.connect('game.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        money INTEGER DEFAULT 100,
        business TEXT DEFAULT 'Нет',
        house TEXT DEFAULT 'Нет',
        clothes TEXT DEFAULT 'Нет',
        clan TEXT DEFAULT 'Нет',
        job TEXT DEFAULT 'Безработный',
        last_bonus INTEGER DEFAULT 0,
        last_work INTEGER DEFAULT 0,
        last_mafia INTEGER DEFAULT 0
    )
""")
conn.commit()

def reg_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            "money": row[1], "business": row[2], "house": row[3],
            "clothes": row[4], "clan": row[5], "job": row[6],
            "last_bonus": row[7], "last_work": row[8], "last_mafia": row[9]
        }
    return {"money": 0, "business": "Нет", "house": "Нет", "clothes": "Нет", "clan": "Нет", "job": "Безработный"}

def add_money(user_id, amount):
    reg_user(user_id)
    cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def set_job(user_id, job_name):
    cursor.execute("UPDATE users SET job = ? WHERE user_id = ?", (job_name, user_id))
    conn.commit()

def set_clan(user_id, clan_name):
    cursor.execute("UPDATE users SET clan = ? WHERE user_id = ?", (clan_name, user_id))
    conn.commit()

def buy_item(user_id, item_type, item_name):
    cursor.execute(f"UPDATE users SET {item_type} = ? WHERE user_id = ?", (item_name, user_id))
    conn.commit()

def transfer_money(from_id, to_id, amount):
    user = get_user(from_id)
    if user['money'] >= amount:
        add_money(from_id, -amount)
        add_money(to_id, amount)
        return True
    return False

def can_work(user_id):
    user = get_user(user_id)
    if time.time() - user['last_work'] > 3600:
        cursor.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (int(time.time()), user_id))
        conn.commit()
        return True
    return False

def can_mafia(user_id):
    user = get_user(user_id)
    if time.time() - user['last_mafia'] > 1800:
        cursor.execute("UPDATE users SET last_mafia = ? WHERE user_id = ?", (int(time.time()), user_id))
        conn.commit()
        return True
    return False

def can_bonus(user_id):
    user = get_user(user_id)
    if time.time() - user['last_bonus'] > 86400:
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (int(time.time()), user_id))
        conn.commit()
        return True
    return False

def get_top(limit=10):
    cursor.execute("SELECT user_id, money FROM users ORDER BY money DESC LIMIT ?", (limit,))
    return cursor.fetchall()

# === ИНИЦИАЛИЗАЦИЯ LONGPOLL С GROUP_ID ===
try:
    longpoll = VkLongPoll(vk_session, group_id=GROUP_ID, wait=25)
    print("✅ LongPoll запущен с GROUP_ID")
except Exception as e:
    print(f"❌ Ошибка LongPoll: {e}")
    exit(1)

# === ЦЕНЫ И РАБОТЫ ===
PRICES = {
    "business": {"Ларёк": 100, "Магазин": 500, "Ресторан": 2000},
    "house": {"Квартира": 200, "Дом": 1000, "Вилла": 5000},
    "clothes": {"Футболка": 50, "Костюм": 300, "Бренд": 1500}
}

JOBS = {
    "Безработный": 0,
    "Курьер": 20,
    "Официант": 40,
    "Менеджер": 80,
    "Бизнесмен": 150
}

pending_clans = {}

# === КЛАВИАТУРЫ ===
def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('👤 Профиль', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('💰 Баланс', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('🛒 Магазин', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('💼 Работа', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('🔫 Мафия', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button('🎁 Бонус', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('🏆 Топ', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('👥 Клан', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('📋 Помощь', color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def get_shop_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('🏪 Бизнес', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('🏠 Дома', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('👕 Одежда', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

# === FLASK ДЛЯ АНТИ-СНА ===
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# === ОСНОВНОЙ ЦИКЛ ===
def run_bot():
    print("🤖 Бот запущен и слушает сообщения...")
    print("📝 Отправьте 'меню' в сообщения группы")
    
    for event in longpoll.listen():
        print(f"📨 Событие: {event.type}")
        
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text.lower() if event.text else ""
            peer_id = event.peer_id
            
            print(f"💬 {user_id}: {text}")
            
            reg_user(user_id)
            user = get_user(user_id)
            
            # === КОМАНДЫ ===
            if text in ['начать', 'старт', 'меню']:
                vk.messages.send(peer_id=peer_id, message="🎮 Добро пожаловать в игру!", keyboard=get_main_keyboard(), random_id=get_random_id())
            
            elif text == '👤 профиль':
                msg = f"👤 Профиль:\n💰 Баланс: {user['money']} руб.\n💼 Бизнес: {user['business']}\n🏠 Дом: {user['house']}\n👕 Одежда: {user['clothes']}\n👥 Клан: {user['clan']}\n💪 Работа: {user['job']}"
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text == '💰 баланс':
                vk.messages.send(peer_id=peer_id, message=f"💰 Баланс: {user['money']} руб.", random_id=get_random_id())
            
            elif text == '💼 работа':
                if user['job'] == 'Безработный':
                    keyboard = VkKeyboard(one_time=True)
                    for job in JOBS:
                        if job != 'Безработный':
                            keyboard.add_button(f"Устроиться {job}", color=VkKeyboardColor.PRIMARY)
                    keyboard.add_line()
                    keyboard.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
                    vk.messages.send(peer_id=peer_id, message="Выберите работу:", keyboard=keyboard.get_keyboard(), random_id=get_random_id())
                else:
                    if can_work(user_id):
                        salary = JOBS[user['job']]
                        add_money(user_id, salary)
                        vk.messages.send(peer_id=peer_id, message=f"💼 +{salary} руб.", keyboard=get_main_keyboard(), random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=peer_id, message="⏳ Работать можно раз в час!", random_id=get_random_id())
            
            elif text.startswith('устроиться'):
                job = text.replace('устроиться ', '')
                if job in JOBS:
                    set_job(user_id, job)
                    vk.messages.send(peer_id=peer_id, message=f"✅ Вы устроились: {job}", keyboard=get_main_keyboard(), random_id=get_random_id())
            
            elif text == '🔫 мафия':
                if can_mafia(user_id):
                    outcomes = [
                        ("💰 Ограбление банка!", random.randint(100, 300)),
                        ("💊 Продажа товара", random.randint(50, 150)),
                        ("🚓 Полиция!", -random.randint(50, 200)),
                        ("💀 Конкуренты", -random.randint(30, 100)),
                        ("🍀 Джекпот!", random.randint(500, 1000))
                    ]
                    msg, amount = random.choice(outcomes)
                    add_money(user_id, amount)
                    vk.messages.send(peer_id=peer_id, message=f"🔫 {msg} ({'+' if amount > 0 else ''}{amount} руб.)", keyboard=get_main_keyboard(), random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=peer_id, message="⏳ Мафия доступна раз в 30 мин!", random_id=get_random_id())
            
            elif text == '🎁 бонус':
                if can_bonus(user_id):
                    bonus = random.randint(25, 75)
                    add_money(user_id, bonus)
                    vk.messages.send(peer_id=peer_id, message=f"🎁 +{bonus} руб.", keyboard=get_main_keyboard(), random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=peer_id, message="⏳ Бонус раз в 24 часа!", random_id=get_random_id())
            
            elif text == '🛒 магазин':
                vk.messages.send(peer_id=peer_id, message="🛒 Категория:", keyboard=get_shop_keyboard(), random_id=get_random_id())
            
            elif text == '🏪 бизнес':
                msg = "🏪 Бизнесы:\n" + "\n".join([f"{n}: {p} руб." for n, p in PRICES['business'].items()])
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text == '🏠 дома':
                msg = "🏠 Дома:\n" + "\n".join([f"{n}: {p} руб." for n, p in PRICES['house'].items()])
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text == '👕 одежда':
                msg = "👕 Одежда:\n" + "\n".join([f"{n}: {p} руб." for n, p in PRICES['clothes'].items()])
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text.startswith('купить бизнес '):
                item = text.replace('купить бизнес ', '').capitalize()
                if item in PRICES['business']:
                    price = PRICES['business'][item]
                    if user['money'] >= price:
                        add_money(user_id, -price)
                        buy_item(user_id, 'business', item)
                        vk.messages.send(peer_id=peer_id, message=f"✅ Куплено: {item}", random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
            
            elif text.startswith('купить дом '):
                item = text.replace('купить дом ', '').capitalize()
                if item in PRICES['house']:
                    price = PRICES['house'][item]
                    if user['money'] >= price:
                        add_money(user_id, -price)
                        buy_item(user_id, 'house', item)
                        vk.messages.send(peer_id=peer_id, message=f"✅ Куплено: {item}", random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
            
            elif text.startswith('купить одежду '):
                item = text.replace('купить одежду ', '').capitalize()
                if item in PRICES['clothes']:
                    price = PRICES['clothes'][item]
                    if user['money'] >= price:
                        add_money(user_id, -price)
                        buy_item(user_id, 'clothes', item)
                        vk.messages.send(peer_id=peer_id, message=f"✅ Куплено: {item}", random_id=get_random_id())
                    else:
                        vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
            
            elif text == '🏆 топ':
                top = get_top(10)
                msg = "🏆 Топ-10:\n"
                for i, (uid, money) in enumerate(top, 1):
                    try:
                        user_info = vk.users.get(user_ids=uid)[0]
                        name = f"{user_info['first_name']} {user_info['last_name']}"
                    except:
                        name = f"ID{uid}"
                    msg += f"{i}. {name}: {money} руб.\n"
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text.startswith('перевести'):
                parts = text.split()
                if len(parts) >= 3:
                    try:
                        amount = int(parts[1])
                        target_str = parts[2]
                        if '[id' in target_str:
                            target_id = int(target_str.split('|')[0].replace('[id', ''))
                        else:
                            target_id = int(target_str)
                        
                        if target_id == user_id:
                            vk.messages.send(peer_id=peer_id, message="❌ Нельзя себе!", random_id=get_random_id())
                        elif transfer_money(user_id, target_id, amount):
                            vk.messages.send(peer_id=peer_id, message=f"✅ Переведено {amount} руб.", random_id=get_random_id())
                        else:
                            vk.messages.send(peer_id=peer_id, message="❌ Недостаточно средств!", random_id=get_random_id())
                    except:
                        vk.messages.send(peer_id=peer_id, message="❌ Формат: перевести [сумма] [id]", random_id=get_random_id())
            
            elif text == '📋 помощь':
                msg = "📋 Команды: Профиль, Баланс, Магазин, Работа, Мафия, Бонус, Топ, Перевести"
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            elif text == '⬅️ назад':
                vk.messages.send(peer_id=peer_id, message="🏠 Главное меню:", keyboard=get_main_keyboard(), random_id=get_random_id())

# === ЗАПУСК ===
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    run_bot()
