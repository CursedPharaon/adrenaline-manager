import vk_api
import random
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from database import BotDB

# === НАСТРОЙКИ ===
VK_TOKEN = "ВАШ_ТОКЕН_ГРУППЫ"

# Инициализация
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
db = BotDB()

# Цены и предметы
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

# === ГЛАВНОЕ МЕНЮ ===
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

def get_clan_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Создать клан', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('Вступить в клан', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('Топ кланов', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

# === ОСНОВНОЙ ЦИКЛ ===
print("🤖 Бот запущен!")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.lower()
        peer_id = event.peer_id
        
        db.reg_user(user_id)
        user = db.get_user(user_id)
        
        # === ГЛАВНЫЕ КОМАНДЫ ===
        if text in ['начать', 'старт', 'меню']:
            vk.messages.send(
                peer_id=peer_id,
                message="🎮 Добро пожаловать в игру! Выберите действие:",
                keyboard=get_main_keyboard(),
                random_id=get_random_id()
            )
        
        elif text == '👤 профиль':
            msg = f"""
👤 Профиль игрока:
├ 💰 Баланс: {user['money']} руб.
├ 💼 Бизнес: {user['business']}
├ 🏠 Дом: {user['house']}
├ 👕 Одежда: {user['clothes']}
├ 👥 Клан: {user['clan']}
└ 💪 Работа: {user['job']}
            """
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        elif text == '💰 баланс':
            vk.messages.send(
                peer_id=peer_id,
                message=f"💰 Ваш баланс: {user['money']} руб.",
                random_id=get_random_id()
            )
        
        # === РАБОТА ===
        elif text == '💼 работа':
            if user['job'] == 'Безработный':
                keyboard = VkKeyboard(one_time=True)
                for job, salary in JOBS.items():
                    if job != 'Безработный':
                        keyboard.add_button(f"Устроиться {job}", color=VkKeyboardColor.PRIMARY)
                keyboard.add_line()
                keyboard.add_button('⬅️ Назад', color=VkKeyboardColor.NEGATIVE)
                vk.messages.send(
                    peer_id=peer_id,
                    message="Выберите работу:",
                    keyboard=keyboard.get_keyboard(),
                    random_id=get_random_id()
                )
            else:
                if db.can_work(user_id):
                    salary = JOBS[user['job']]
                    db.add_money(user_id, salary)
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"💼 Вы поработали {user['job']} и заработали {salary} руб.",
                        keyboard=get_main_keyboard(),
                        random_id=get_random_id()
                    )
                else:
                    vk.messages.send(
                        peer_id=peer_id,
                        message="⏳ Работать можно раз в час!",
                        random_id=get_random_id()
                    )
        
        elif text.startswith('устроиться'):
            job = text.replace('устроиться ', '')
            if job in JOBS:
                db.set_job(user_id, job)
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"✅ Вы устроились на работу: {job}",
                    keyboard=get_main_keyboard(),
                    random_id=get_random_id()
                )
        
        # === МАФИЯ ===
        elif text == '🔫 мафия':
            if db.can_mafia(user_id):
                outcomes = [
                    ("💰 Вы ограбили банк!", random.randint(100, 300)),
                    ("💊 Вы продали партию товара", random.randint(50, 150)),
                    ("🚓 Вас поймала полиция!", -random.randint(50, 200)),
                    ("💀 Вас убили конкуренты", -random.randint(30, 100)),
                    ("🍀 Вы сорвали джекпот!", random.randint(500, 1000))
                ]
                msg, amount = random.choice(outcomes)
                db.add_money(user_id, amount)
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"🔫 {msg} ({'+' if amount > 0 else ''}{amount} руб.)",
                    keyboard=get_main_keyboard(),
                    random_id=get_random_id()
                )
            else:
                vk.messages.send(
                    peer_id=peer_id,
                    message="⏳ Мафия доступна раз в 30 минут!",
                    random_id=get_random_id()
                )
        
        # === БОНУС ===
        elif text == '🎁 бонус':
            if db.can_get_bonus(user_id):
                bonus = random.randint(25, 75)
                db.add_money(user_id, bonus)
                vk.messages.send(
                    peer_id=peer_id,
                    message=f"🎁 Ежедневный бонус: {bonus} руб.",
                    keyboard=get_main_keyboard(),
                    random_id=get_random_id()
                )
            else:
                vk.messages.send(
                    peer_id=peer_id,
                    message="⏳ Бонус доступен раз в 24 часа!",
                    random_id=get_random_id()
                )
        
        # === МАГАЗИН ===
        elif text == '🛒 магазин':
            vk.messages.send(
                peer_id=peer_id,
                message="🛒 Выберите категорию:",
                keyboard=get_shop_keyboard(),
                random_id=get_random_id()
            )
        
        elif text == '🏪 бизнес':
            msg = "🏪 Доступные бизнесы:\n"
            for name, price in PRICES['business'].items():
                msg += f"├ {name}: {price} руб.\n"
            msg += "└ Напишите: купить бизнес [название]"
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        elif text == '🏠 дома':
            msg = "🏠 Доступные дома:\n"
            for name, price in PRICES['house'].items():
                msg += f"├ {name}: {price} руб.\n"
            msg += "└ Напишите: купить дом [название]"
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        elif text == '👕 одежда':
            msg = "👕 Доступная одежда:\n"
            for name, price in PRICES['clothes'].items():
                msg += f"├ {name}: {price} руб.\n"
            msg += "└ Напишите: купить одежду [название]"
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        elif text.startswith('купить бизнес '):
            item = text.replace('купить бизнес ', '').capitalize()
            if item in PRICES['business']:
                price = PRICES['business'][item]
                if user['money'] >= price:
                    db.add_money(user_id, -price)
                    db.buy_item(user_id, 'business', item)
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Вы купили бизнес: {item}",
                        random_id=get_random_id()
                    )
                else:
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"❌ Недостаточно денег! Нужно {price} руб.",
                        random_id=get_random_id()
                    )
        
        elif text.startswith('купить дом '):
            item = text.replace('купить дом ', '').capitalize()
            if item in PRICES['house']:
                price = PRICES['house'][item]
                if user['money'] >= price:
                    db.add_money(user_id, -price)
                    db.buy_item(user_id, 'house', item)
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Вы купили дом: {item}",
                        random_id=get_random_id()
                    )
                else:
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"❌ Недостаточно денег! Нужно {price} руб.",
                        random_id=get_random_id()
                    )
        
        elif text.startswith('купить одежду '):
            item = text.replace('купить одежду ', '').capitalize()
            if item in PRICES['clothes']:
                price = PRICES['clothes'][item]
                if user['money'] >= price:
                    db.add_money(user_id, -price)
                    db.buy_item(user_id, 'clothes', item)
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"✅ Вы купили одежду: {item}",
                        random_id=get_random_id()
                    )
                else:
                    vk.messages.send(
                        peer_id=peer_id,
                        message=f"❌ Недостаточно денег! Нужно {price} руб.",
                        random_id=get_random_id()
                    )
        
        # === ТОП ===
        elif text == '🏆 топ':
            top = db.get_top(10)
            msg = "🏆 Топ-10 богачей:\n"
            for i, (uid, money) in enumerate(top, 1):
                try:
                    user_info = vk.users.get(user_ids=uid)[0]
                    name = f"{user_info['first_name']} {user_info['last_name']}"
                except:
                    name = f"ID{uid}"
                msg += f"{i}. {name}: {money} руб.\n"
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        # === КЛАНЫ ===
        elif text == '👥 клан':
            vk.messages.send(
                peer_id=peer_id,
                message="👥 Управление кланом:",
                keyboard=get_clan_keyboard(),
                random_id=get_random_id()
            )
        
        elif text == 'создать клан':
            if user['money'] >= 500:
                vk.messages.send(
                    peer_id=peer_id,
                    message="Введите название клана (одно слово):",
                    random_id=get_random_id()
                )
                # Здесь нужен FSM, но для простоты просто запомним
            else:
                vk.messages.send(
                    peer_id=peer_id,
                    message="❌ Для создания клана нужно 500 руб!",
                    random_id=get_random_id()
                )
        
        elif text == 'топ кланов':
            top = db.get_clan_top()
            msg = "🏆 Топ кланов:\n"
            for i, (clan, total) in enumerate(top, 1):
                msg += f"{i}. {clan}: {total} руб.\n"
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        # === ПЕРЕВОД ДЕНЕГ ===
        elif text.startswith('перевести'):
            parts = text.split()
            if len(parts) >= 3:
                try:
                    amount = int(parts[1])
                    # Извлекаем ID из упоминания или просто число
                    target_str = parts[2]
                    target_id = int(target_str.replace('[id', '').split('|')[0])
                    
                    if db.transfer_money(user_id, target_id, amount):
                        vk.messages.send(
                            peer_id=peer_id,
                            message=f"✅ Переведено {amount} руб.",
                            random_id=get_random_id()
                        )
                    else:
                        vk.messages.send(
                            peer_id=peer_id,
                            message="❌ Недостаточно средств!",
                            random_id=get_random_id()
                        )
                except:
                    vk.messages.send(
                        peer_id=peer_id,
                        message="❌ Формат: перевести [сумма] [id]",
                        random_id=get_random_id()
                    )
        
        # === ПОМОЩЬ ===
        elif text == '📋 помощь':
            msg = """
📋 Доступные команды:
├ 👤 Профиль - информация о персонаже
├ 💰 Баланс - текущий баланс
├ 🛒 Магазин - покупка имущества
├ 💼 Работа - заработок (раз в час)
├ 🔫 Мафия - рискованный заработок (раз в 30 мин)
├ 🎁 Бонус - ежедневный бонус
├ 🏆 Топ - рейтинг богачей
├ 👥 Клан - управление кланом
└ Перевести [сумма] [id] - перевод денег
            """
            vk.messages.send(peer_id=peer_id, message=msg, random_id=get_random_id())
        
        # === НАЗАД ===
        elif text == '⬅️ назад':
            vk.messages.send(
                peer_id=peer_id,
                message="🏠 Главное меню:",
                keyboard=get_main_keyboard(),
                random_id=get_random_id()
            )
        
        else:
            vk.messages.send(
                peer_id=peer_id,
                message="❓ Неизвестная команда. Напишите 'Меню' для списка команд.",
                random_id=get_random_id()
            )