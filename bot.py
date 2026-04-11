import vk_api
import random
import time
import os
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# === ТОКЕН ===
VK_TOKEN = os.environ.get('VK_TOKEN')
if not VK_TOKEN:
    print("Нет токена!")
    exit(1)

# === VK API ===
vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.199')
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# === ХРАНИЛИЩЕ ДАННЫХ В ПАМЯТИ ===
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

# === ЗАПУСК ===
print("🤖 Бот запущен!")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        uid = event.user_id
        text = event.text.lower().strip() if event.text else ""
        user = get_user(uid)
        
        # === МЕНЮ ===
        if text in ['меню', 'начать', 'старт', 'menu']:
            vk.messages.send(
                peer_id=uid,
                message="🎮 Добро пожаловать!",
                keyboard=main_keyboard(),
                random_id=get_random_id()
            )
        
        # === ПРОФИЛЬ ===
        elif text in ['профиль', '👤 профиль']:
            msg = f"""👤 Профиль:
💰 Деньги: {user['money']} руб.
💼 Работа: {user['job']}
🏪 Бизнес: {user['business']}
🏠 Дом: {user['house']}
👕 Одежда: {user['clothes']}"""
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === БАЛАНС ===
        elif text in ['баланс', '💰 баланс']:
            vk.messages.send(peer_id=uid, message=f"💰 {user['money']} руб.", random_id=get_random_id())
        
        # === РАБОТА ===
        elif text in ['работа', '💼 работа']:
            if user['job'] == 'Безработный':
                k = VkKeyboard(one_time=True)
                for job in JOBS:
                    k.add_button(f"Устроиться {job}", VkKeyboardColor.PRIMARY)
                k.add_line()
                k.add_button('⬅️ Назад', VkKeyboardColor.NEGATIVE)
                vk.messages.send(peer_id=uid, message="Выберите работу:", keyboard=k.get_keyboard(), random_id=get_random_id())
            else:
                if time.time() - user['last_work'] >= 3600:
                    salary = JOBS[user['job']]
                    user['money'] += salary
                    user['last_work'] = time.time()
                    vk.messages.send(peer_id=uid, message=f"💼 +{salary} руб.", keyboard=main_keyboard(), random_id=get_random_id())
                else:
                    remain = int(3600 - (time.time() - user['last_work']))
                    vk.messages.send(peer_id=uid, message=f"⏳ Ждите {remain // 60} мин.", random_id=get_random_id())
        
        # === УСТРОИТЬСЯ ===
        elif text.startswith('устроиться '):
            job = text.replace('устроиться ', '').capitalize()
            if job in JOBS:
                user['job'] = job
                vk.messages.send(peer_id=uid, message=f"✅ Вы устроились: {job}", keyboard=main_keyboard(), random_id=get_random_id())
        
        # === МАФИЯ ===
        elif text in ['мафия', '🔫 мафия']:
            if time.time() - user['last_mafia'] >= 1800:
                r = random.randint(1, 100)
                if r <= 40:
                    win = random.randint(50, 200)
                    user['money'] += win
                    msg = f"💰 Ограбление! +{win} руб."
                elif r <= 70:
                    lose = random.randint(30, 100)
                    user['money'] = max(0, user['money'] - lose)
                    msg = f"🚓 Полиция! -{lose} руб."
                else:
                    jackpot = random.randint(300, 1000)
                    user['money'] += jackpot
                    msg = f"🍀 ДЖЕКПОТ! +{jackpot} руб."
                user['last_mafia'] = time.time()
                vk.messages.send(peer_id=uid, message=f"🔫 {msg}", keyboard=main_keyboard(), random_id=get_random_id())
            else:
                remain = int(1800 - (time.time() - user['last_mafia']))
                vk.messages.send(peer_id=uid, message=f"⏳ Ждите {remain // 60} мин.", random_id=get_random_id())
        
        # === БОНУС ===
        elif text in ['бонус', '🎁 бонус']:
            if time.time() - user['last_bonus'] >= 86400:
                bonus = random.randint(25, 75)
                user['money'] += bonus
                user['last_bonus'] = time.time()
                vk.messages.send(peer_id=uid, message=f"🎁 +{bonus} руб.", keyboard=main_keyboard(), random_id=get_random_id())
            else:
                vk.messages.send(peer_id=uid, message="⏳ Бонус раз в 24 часа!", random_id=get_random_id())
        
        # === МАГАЗИН ===
        elif text in ['магазин', '🛒 магазин']:
            vk.messages.send(peer_id=uid, message="🛒 Категория:", keyboard=shop_keyboard(), random_id=get_random_id())
        
        # === БИЗНЕС ===
        elif text in ['бизнес', '🏪 бизнес']:
            msg = "🏪 Бизнесы:\n"
            for name, price in BUSINESS_PRICES.items():
                msg += f"{name}: {price} руб.\n"
            msg += "\nНапишите: купить бизнес [название]"
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === ДОМА ===
        elif text in ['дома', '🏠 дома']:
            msg = "🏠 Дома:\n"
            for name, price in HOUSE_PRICES.items():
                msg += f"{name}: {price} руб.\n"
            msg += "\nНапишите: купить дом [название]"
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === ОДЕЖДА ===
        elif text in ['одежда', '👕 одежда']:
            msg = "👕 Одежда:\n"
            for name, price in CLOTHES_PRICES.items():
                msg += f"{name}: {price} руб.\n"
            msg += "\nНапишите: купить одежду [название]"
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === КУПИТЬ БИЗНЕС ===
        elif text.startswith('купить бизнес '):
            item = text.replace('купить бизнес ', '').capitalize()
            if item in BUSINESS_PRICES:
                price = BUSINESS_PRICES[item]
                if user['money'] >= price:
                    user['money'] -= price
                    user['business'] = item
                    vk.messages.send(peer_id=uid, message=f"✅ Куплено: {item}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=uid, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
        
        # === КУПИТЬ ДОМ ===
        elif text.startswith('купить дом '):
            item = text.replace('купить дом ', '').capitalize()
            if item in HOUSE_PRICES:
                price = HOUSE_PRICES[item]
                if user['money'] >= price:
                    user['money'] -= price
                    user['house'] = item
                    vk.messages.send(peer_id=uid, message=f"✅ Куплено: {item}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=uid, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
        
        # === КУПИТЬ ОДЕЖДУ ===
        elif text.startswith('купить одежду '):
            item = text.replace('купить одежду ', '').capitalize()
            if item in CLOTHES_PRICES:
                price = CLOTHES_PRICES[item]
                if user['money'] >= price:
                    user['money'] -= price
                    user['clothes'] = item
                    vk.messages.send(peer_id=uid, message=f"✅ Куплено: {item}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=uid, message=f"❌ Нужно {price} руб.", random_id=get_random_id())
        
        # === ТОП ===
        elif text in ['топ', '🏆 топ']:
            sorted_users = sorted(users.items(), key=lambda x: x[1]['money'], reverse=True)[:10]
            if sorted_users:
                msg = "🏆 Топ-10:\n"
                for i, (u, data) in enumerate(sorted_users, 1):
                    try:
                        info = vk.users.get(user_ids=u)[0]
                        name = f"{info['first_name']} {info['last_name']}"
                    except:
                        name = f"ID{u}"
                    msg += f"{i}. {name}: {data['money']} руб.\n"
            else:
                msg = "🏆 Пока пусто!"
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === ПЕРЕВОД ===
        elif text.startswith('перевести '):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    amount = int(parts[1])
                    target = parts[2]
                    if '[id' in target:
                        target_id = int(target.split('|')[0].replace('[id', ''))
                    else:
                        target_id = int(target)
                    
                    if target_id == uid:
                        vk.messages.send(peer_id=uid, message="❌ Нельзя себе!", random_id=get_random_id())
                    elif user['money'] >= amount:
                        user['money'] -= amount
                        target_user = get_user(target_id)
                        target_user['money'] += amount
                        vk.messages.send(peer_id=uid, message=f"✅ {amount} руб. переведено!", random_id=get_random_id())
                        try:
                            vk.messages.send(user_id=target_id, message=f"💰 Вам перевели {amount} руб.", random_id=get_random_id())
                        except:
                            pass
                    else:
                        vk.messages.send(peer_id=uid, message="❌ Мало денег!", random_id=get_random_id())
                except:
                    vk.messages.send(peer_id=uid, message="❌ Формат: перевести 100 id123", random_id=get_random_id())
        
        # === ПОМОЩЬ ===
        elif text in ['помощь', '📋 помощь']:
            msg = """📋 Команды:
👤 Профиль
💰 Баланс
💼 Работа
🔫 Мафия
🎁 Бонус
🛒 Магазин
🏆 Топ
Перевести [сумма] [id]"""
            vk.messages.send(peer_id=uid, message=msg, random_id=get_random_id())
        
        # === НАЗАД ===
        elif text in ['назад', '⬅️ назад']:
            vk.messages.send(peer_id=uid, message="🏠 Меню:", keyboard=main_keyboard(), random_id=get_random_id())
        
        # === НЕИЗВЕСТНАЯ КОМАНДА ===
        else:
            vk.messages.send(peer_id=uid, message="❓ Напишите 'меню'", random_id=get_random_id())
