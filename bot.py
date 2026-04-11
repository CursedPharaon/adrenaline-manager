import vk_api
import random
import time
import os
from threading import Thread
from flask import Flask
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

# === FLASK ===
app = Flask(__name__)

@app.route('/')
def home():
    return "OK"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# === ТОКЕН И ГРУППА ===
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')

if not VK_TOKEN or not GROUP_ID:
    print("❌ Нет VK_TOKEN или GROUP_ID!")
    exit(1)

GROUP_ID = int(GROUP_ID)
print(f"✅ Токен: {len(VK_TOKEN)} символов, Группа: {GROUP_ID}")

# === VK API ===
vk_session = vk_api.VkApi(token=VK_TOKEN, api_version='5.199')
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID)

# === ДАННЫЕ ===
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
BUSINESS = {"Ларёк": 100, "Магазин": 500, "Ресторан": 2000}
HOUSE = {"Квартира": 200, "Дом": 1000, "Вилла": 5000}
CLOTHES = {"Футболка": 50, "Костюм": 300, "Бренд": 1500}

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

# === БОТ ===
print("🤖 Запуск бота...")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.obj['message']
        uid = msg['from_id']
        text = msg['text'].lower().strip()
        peer_id = msg['peer_id']
        user = get_user(uid)
        
        print(f"📨 {uid}: {text}")
        
        # === МЕНЮ ===
        if text in ['меню', 'начать', 'старт', 'menu']:
            vk.messages.send(
                peer_id=peer_id,
                message="🎮 Добро пожаловать!",
                keyboard=main_keyboard(),
                random_id=get_random_id()
            )
        
        # === ПРОФИЛЬ ===
        elif text in ['профиль', '👤 профиль']:
            m = f"👤 Профиль\n💰 {user['money']} руб.\n💼 {user['job']}\n🏪 {user['business']}\n🏠 {user['house']}\n👕 {user['clothes']}"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === БАЛАНС ===
        elif text in ['баланс', '💰 баланс']:
            vk.messages.send(peer_id=peer_id, message=f"💰 {user['money']} руб.", random_id=get_random_id())
        
        # === РАБОТА ===
        elif text in ['работа', '💼 работа']:
            if user['job'] == 'Безработный':
                k = VkKeyboard(one_time=True)
                for j in JOBS:
                    k.add_button(f"Устроиться {j}", VkKeyboardColor.PRIMARY)
                k.add_line()
                k.add_button('⬅️ Назад', VkKeyboardColor.NEGATIVE)
                vk.messages.send(peer_id=peer_id, message="Выберите:", keyboard=k.get_keyboard(), random_id=get_random_id())
            else:
                if time.time() - user['last_work'] >= 3600:
                    s = JOBS[user['job']]
                    user['money'] += s
                    user['last_work'] = time.time()
                    vk.messages.send(peer_id=peer_id, message=f"💼 +{s} руб.", keyboard=main_keyboard(), random_id=get_random_id())
                else:
                    r = int(3600 - (time.time() - user['last_work']))
                    vk.messages.send(peer_id=peer_id, message=f"⏳ Ждите {r//60} мин.", random_id=get_random_id())
        
        # === УСТРОИТЬСЯ ===
        elif text.startswith('устроиться '):
            j = text.replace('устроиться ', '').capitalize()
            if j in JOBS:
                user['job'] = j
                vk.messages.send(peer_id=peer_id, message=f"✅ {j}", keyboard=main_keyboard(), random_id=get_random_id())
        
        # === МАФИЯ ===
        elif text in ['мафия', '🔫 мафия']:
            if time.time() - user['last_mafia'] >= 1800:
                r = random.randint(1, 100)
                if r <= 40:
                    w = random.randint(50, 200)
                    user['money'] += w
                    m = f"💰 Ограбление! +{w}"
                elif r <= 70:
                    l = random.randint(30, 100)
                    user['money'] = max(0, user['money'] - l)
                    m = f"🚓 Полиция! -{l}"
                else:
                    j = random.randint(300, 1000)
                    user['money'] += j
                    m = f"🍀 ДЖЕКПОТ! +{j}"
                user['last_mafia'] = time.time()
                vk.messages.send(peer_id=peer_id, message=f"🔫 {m}", keyboard=main_keyboard(), random_id=get_random_id())
            else:
                r = int(1800 - (time.time() - user['last_mafia']))
                vk.messages.send(peer_id=peer_id, message=f"⏳ Ждите {r//60} мин.", random_id=get_random_id())
        
        # === БОНУС ===
        elif text in ['бонус', '🎁 бонус']:
            if time.time() - user['last_bonus'] >= 86400:
                b = random.randint(25, 75)
                user['money'] += b
                user['last_bonus'] = time.time()
                vk.messages.send(peer_id=peer_id, message=f"🎁 +{b} руб.", keyboard=main_keyboard(), random_id=get_random_id())
            else:
                vk.messages.send(peer_id=peer_id, message="⏳ Раз в 24 часа!", random_id=get_random_id())
        
        # === МАГАЗИН ===
        elif text in ['магазин', '🛒 магазин']:
            vk.messages.send(peer_id=peer_id, message="🛒 Категория:", keyboard=shop_keyboard(), random_id=get_random_id())
        
        # === БИЗНЕС ===
        elif text in ['бизнес', '🏪 бизнес']:
            m = "🏪 Бизнесы:\n" + "\n".join([f"{n}: {p} руб." for n, p in BUSINESS.items()])
            m += "\n\nкупить бизнес [название]"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === ДОМА ===
        elif text in ['дома', '🏠 дома']:
            m = "🏠 Дома:\n" + "\n".join([f"{n}: {p} руб." for n, p in HOUSE.items()])
            m += "\n\nкупить дом [название]"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === ОДЕЖДА ===
        elif text in ['одежда', '👕 одежда']:
            m = "👕 Одежда:\n" + "\n".join([f"{n}: {p} руб." for n, p in CLOTHES.items()])
            m += "\n\nкупить одежду [название]"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === КУПИТЬ БИЗНЕС ===
        elif text.startswith('купить бизнес '):
            i = text.replace('купить бизнес ', '').capitalize()
            if i in BUSINESS:
                p = BUSINESS[i]
                if user['money'] >= p:
                    user['money'] -= p
                    user['business'] = i
                    vk.messages.send(peer_id=peer_id, message=f"✅ {i}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {p} руб.", random_id=get_random_id())
        
        # === КУПИТЬ ДОМ ===
        elif text.startswith('купить дом '):
            i = text.replace('купить дом ', '').capitalize()
            if i in HOUSE:
                p = HOUSE[i]
                if user['money'] >= p:
                    user['money'] -= p
                    user['house'] = i
                    vk.messages.send(peer_id=peer_id, message=f"✅ {i}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {p} руб.", random_id=get_random_id())
        
        # === КУПИТЬ ОДЕЖДУ ===
        elif text.startswith('купить одежду '):
            i = text.replace('купить одежду ', '').capitalize()
            if i in CLOTHES:
                p = CLOTHES[i]
                if user['money'] >= p:
                    user['money'] -= p
                    user['clothes'] = i
                    vk.messages.send(peer_id=peer_id, message=f"✅ {i}", random_id=get_random_id())
                else:
                    vk.messages.send(peer_id=peer_id, message=f"❌ Нужно {p} руб.", random_id=get_random_id())
        
        # === ТОП ===
        elif text in ['топ', '🏆 топ']:
            s = sorted(users.items(), key=lambda x: x[1]['money'], reverse=True)[:10]
            if s:
                m = "🏆 Топ-10:\n"
                for i, (u, d) in enumerate(s, 1):
                    try:
                        n = f"{vk.users.get(user_ids=u)[0]['first_name']}"
                    except:
                        n = f"ID{u}"
                    m += f"{i}. {n}: {d['money']} руб.\n"
            else:
                m = "🏆 Пусто"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === ПЕРЕВОД ===
        elif text.startswith('перевести '):
            p = text.split()
            if len(p) >= 3:
                try:
                    a = int(p[1])
                    t = p[2]
                    tid = int(t.split('|')[0].replace('[id', '')) if '[id' in t else int(t)
                    if tid == uid:
                        vk.messages.send(peer_id=peer_id, message="❌ Нельзя себе!", random_id=get_random_id())
                    elif user['money'] >= a:
                        user['money'] -= a
                        get_user(tid)['money'] += a
                        vk.messages.send(peer_id=peer_id, message=f"✅ {a} руб.", random_id=get_random_id())
                        try:
                            vk.messages.send(user_id=tid, message=f"💰 Вам перевели {a} руб.", random_id=get_random_id())
                        except:
                            pass
                    else:
                        vk.messages.send(peer_id=peer_id, message="❌ Мало денег!", random_id=get_random_id())
                except:
                    vk.messages.send(peer_id=peer_id, message="❌ перевести 100 id123", random_id=get_random_id())
        
        # === ПОМОЩЬ ===
        elif text in ['помощь', '📋 помощь']:
            m = "📋 Профиль, Баланс, Работа, Мафия, Бонус, Магазин, Топ, Перевести"
            vk.messages.send(peer_id=peer_id, message=m, random_id=get_random_id())
        
        # === НАЗАД ===
        elif text in ['назад', '⬅️ назад']:
            vk.messages.send(peer_id=peer_id, message="🏠 Меню", keyboard=main_keyboard(), random_id=get_random_id())
        
        # === НЕИЗВЕСТНО ===
        else:
            vk.messages.send(peer_id=peer_id, message="❓ Напишите 'меню'", random_id=get_random_id())

# === ЗАПУСК ===
if __name__ == '__main__':
    Thread(target=run_flask, daemon=True).start()
    print("🚀 БОТ ЗАПУЩЕН! Отправьте 'меню' в ЛС группы!")
    # Запуск бота в основном потоке
    pass
