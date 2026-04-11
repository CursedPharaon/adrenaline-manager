import vk_api
import random
import time
import os
from threading import Thread
from flask import Flask
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# === FLASK ДЛЯ ПОРТА (чтобы Render не ругался) ===
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# === ТОКЕН И ID ГРУППЫ ===
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID') # ОБЯЗАТЕЛЬНО добавьте эту переменную на Render!

if not VK_TOKEN or not GROUP_ID:
    print("❌ Нет VK_TOKEN или GROUP_ID в переменных окружения!")
    exit(1)

print(f"✅ Токен загружен, GROUP_ID: {GROUP_ID}")

# === VK API (используем VkBotLongPoll для групп) ===
vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.199')
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID) # <- Явно передаем ID группы

# === ХРАНИЛИЩЕ ДАННЫХ ===
users = {}

def get_user(uid):
    if uid not in users:
        users[uid] = {
            "money": 100,
            "job": "Безработный",
            "business": "Нет",
            "house": "Нет",
            "clothes": "Нет",
            "last_work": 0,
            "last_mafia": 0,
            "last_bonus": 0
        }
    return users[uid]

# === ЦЕНЫ ===
JOBS = {"Курьер": 20, "Официант": 40, "Менеджер": 80, "Бизнесмен": 150}
BUSINESS_PRICES = {"Ларёк": 100, "Магазин": 500, "Ресторан": 2000}
HOUSE_PRICES = {"Квартира": 200, "Дом": 1000, "Вилла": 5000}
CLOTHES_PRICES = {"Футболка": 50, "Костюм": 300, "Бренд": 1500}

# === КЛАВИАТУРЫ ===
def main_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button('👤 Профиль', VkKeyboardColor.PRIMARY)
    k.add_button('💰 Баланс', VkKeyboardColor.POSITIVE)
    k.add_line()
    k.add_button('💼 Работа', VkKeyboardColor.PRIMARY)
    k.add_button('🔫 Мафия', VkKeyboardColor.NEGATIVE)
    k.add_line()
    k.add_button('🎁 Бонус', VkKeyboardColor.POSITIVE)
    k.add_button('🛒 Магазин', VkKeyboardColor.SECONDARY)
    k.add_line()
    k.add_button('🏆 Топ', VkKeyboardColor.SECONDARY)
    k.add_button('📋 Помощь', VkKeyboardColor.SECONDARY)
    return k.get_keyboard()

def shop_keyboard():
    k = VkKeyboard(one_time=False)
    k.add_button('🏪 Бизнес', VkKeyboardColor.POSITIVE)
    k.add_button('🏠 Дома', VkKeyboardColor.PRIMARY)
    k.add_line()
    k.add_button('👕 Одежда', VkKeyboardColor.SECONDARY)
    k.add_button('⬅️ Назад', VkKeyboardColor.NEGATIVE)
    return k.get_keyboard()

# === ЗАПУСК БОТА ===
def run_bot():
    print("🤖 Бот запущен и слушает сообщения...")
    
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            # VkBotLongPoll не имеет атрибута to_me, он всегда подразумевает обращение к боту
            uid = event.obj['message']['from_id']
            text = event.obj['message']['text'].lower().strip()
            peer_id = event.obj['message']['peer_id'] # Используем peer_id для ответа
            
            user = get_user(uid)
            
            # === ОБРАБОТЧИКИ КОМАНД ===
            if text in ['меню', 'начать', 'старт', 'menu']:
                vk.messages.send(
                    peer_id=peer_id,
                    message="🎮 Добро пожаловать!",
                    keyboard=main_keyboard(),
                    random_id=get_random_id()
                )
            
            # ... (весь остальной код обработки команд: Профиль, Баланс, Работа, Магазин и т.д. остается БЕЗ ИЗМЕНЕНИЙ)
            # Он уже использует uid и peer_id, что правильно.
            elif text in ['профиль', '👤 профиль']:
                msg = f"""👤 Профиль:
💰 Деньги: {user['money']} руб.
💼 Работа: {user['job']}
🏪 Бизнес: {user['business']}
🏠 Дом: {user['house']}
👕 Одежда: {user['clothes']}"""
                vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
            
            # ВАЖНО: Скопируйте сюда все остальные блоки `elif` из предыдущей версии кода (работа, мафия, магазин и т.д.)
            # Они не требуют изменений, просто вставьте их сюда для полноценной работы.

            else:
                vk.messages.send(peer_id=peer_id, message="❓ Напишите 'меню'", random_id=get_random_id())

# === ЗАПУСК ВСЕГО ===
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    run_bot()
