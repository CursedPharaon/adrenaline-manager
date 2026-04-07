import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import time
import re
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

# ================= КОНФИГУРАЦИЯ =================
GROUP_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("VK_GROUP_ID"))
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))

if not GROUP_TOKEN or not GROUP_ID or not BOT_OWNER_ID:
    print("❌ ОШИБКА: Не все переменные окружения заданы!")
    exit(1)
# ===============================================

# Функция создания сессии
def create_session():
    session = vk_api.VkApi(token=GROUP_TOKEN)
    api = session.get_api()
    longpoll = VkBotLongPoll(session, GROUP_ID)
    return session, api, longpoll

# База данных
DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "users": {},
        "silence_mode": {},
        "muted_users": {},
        "vip_chats": {},
        "last_bonus": {}
    }

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
user_data = data["users"]
silence_mode = data.get("silence_mode", {})
muted_users = data.get("muted_users", {})
vip_chats = data.get("vip_chats", {})
last_bonus = data.get("last_bonus", {})

# Словарь ролей
ROLES = {
    0: "👤 Пользователь",
    10: "🛡️ Помощник",
    20: "🔧 Модератор",
    30: "⚡ Администратор",
    50: "👑 Главный админ",
    80: "⭐ Руководитель",
    100: "💎 Владелец"
}

# Цены на VIP
VIP_PRICES = {
    1: 500,
    7: 3000,
    30: 10000
}

# Бонусные суммы
BONUS_RANGE = (50, 500)

def init_user(uid):
    """Инициализирует пользователя в БД"""
    uid_str = str(uid)
    if uid_str not in user_data:
        user_data[uid_str] = {
            "role": 0,
            "warns": 0,
            "money": 0,
            "vip_until": 0,
            "nickname": ""
        }
        save_data()
        print(f"✅ Создан новый пользователь: {uid_str}")
    return user_data[uid_str]

def get_money(uid):
    init_user(uid)
    return user_data[str(uid)].get("money", 0)

def add_money(uid, amount):
    init_user(uid)
    current = get_money(uid)
    new_amount = current + amount
    user_data[str(uid)]["money"] = new_amount
    save_data()
    print(f"💰 {uid} +{amount} = {new_amount}")
    return new_amount

def remove_money(uid, amount):
    init_user(uid)
    current = get_money(uid)
    if current >= amount:
        user_data[str(uid)]["money"] = current - amount
        save_data()
        print(f"💰 {uid} -{amount} = {user_data[str(uid)]['money']}")
        return True
    return False

def is_vip(uid):
    init_user(uid)
    vip_until = user_data[str(uid)].get("vip_until", 0)
    return vip_until > time.time()

def get_vip_days_left(uid):
    init_user(uid)
    vip_until = user_data[str(uid)].get("vip_until", 0)
    if vip_until > time.time():
        return max(1, int((vip_until - time.time()) / 86400))
    return 0

def set_vip(uid, days):
    init_user(uid)
    current_until = user_data[str(uid)].get("vip_until", 0)
    new_until = max(current_until, time.time()) + (days * 86400)
    user_data[str(uid)]["vip_until"] = new_until
    save_data()
    print(f"💎 {uid} купил VIP на {days} дней до {new_until}")
    return new_until

def is_vip_chat(peer_id):
    return str(peer_id) in vip_chats and vip_chats[str(peer_id)]

def set_vip_chat(peer_id, value=True):
    if value:
        vip_chats[str(peer_id)] = True
    else:
        vip_chats.pop(str(peer_id), None)
    save_data()

def can_use_bonus(uid):
    uid_str = str(uid)
    last = last_bonus.get(uid_str, 0)
    return time.time() - last >= 3600

def set_bonus_used(uid):
    last_bonus[str(uid)] = time.time()
    save_data()

def send(peer_id, text, reply_to=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=random.randint(1, 2**31),
            reply_to=reply_to
        )
        print(f"✅ Отправлено в {peer_id}: {text[:50]}")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def kick_user(chat_id, user_id):
    try:
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
        return True
    except:
        return False

def is_chat_admin(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_admin', False) or member.get('is_owner', False)
    except:
        pass
    return False

def is_chat_owner(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_owner', False)
    except:
        pass
    return False

def get_access(peer_id, user_id):
    if user_id == BOT_OWNER_ID:
        return 100
    if is_chat_owner(peer_id, user_id):
        return 100
    if str(user_id) in user_data:
        return user_data[str(user_id)].get("role", 0)
    if is_chat_admin(peer_id, user_id):
        return 50
    return 0

def get_role_name(role):
    return ROLES.get(role, "👤 Пользователь")

def can_assign_role(giver_role, target_role):
    if target_role >= giver_role:
        return False
    if target_role == 100:
        return False
    if giver_role < 30:
        return False
    return True

def is_user_muted(peer_id, user_id):
    key = f"{peer_id}_{user_id}"
    if key in muted_users:
        if muted_users[key] > time.time():
            return True
        else:
            del muted_users[key]
            save_data()
    return False

def mute_user(peer_id, user_id, minutes):
    key = f"{peer_id}_{user_id}"
    muted_users[key] = time.time() + (minutes * 60)
    save_data()

def unmute_user(peer_id, user_id):
    key = f"{peer_id}_{user_id}"
    if key in muted_users:
        del muted_users[key]
        save_data()

def get_target_user(text, event):
    if event.object.message.get('reply_message'):
        return event.object.message['reply_message']['from_id']
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        return int(match.group(1))
    return None

def get_username(user_id):
    try:
        user = vk.users.get(user_ids=user_id, fields='screen_name')
        if user and user[0].get('screen_name'):
            return user[0]['screen_name']
    except:
        pass
    return None

def get_link(user_id):
    username = get_username(user_id)
    if username:
        return f"@{username}"
    return f"[id{user_id}|юзер]"

# ================= ВЕБ-СЕРВЕР =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_web():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ================= ОСНОВНОЙ ЦИКЛ =================
print("=" * 50)
print("✅ Adrenaline Manager ЗАПУЩЕН!")
print(f"👑 Владелец бота: {BOT_OWNER_ID}")
print("=" * 50)

last_processed = {}
PROCESS_TIMEOUT = 3

vk_session, vk, longpoll = create_session()

while True:
    try:
        for event in longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            
            event_id = f"{event.object.message['peer_id']}_{event.object.message['id']}"
            if event_id in last_processed and time.time() - last_processed[event_id] < PROCESS_TIMEOUT:
                continue
            last_processed[event_id] = time.time()
            
            if event.from_user:
                try:
                    vk.messages.send(
                        user_id=event.object.message['from_id'],
                        message="🤖 Я работаю только в беседах!",
                        random_id=random.randint(1, 2**31)
                    )
                except:
                    pass
                continue
            
            if not event.from_chat:
                continue
            
            peer_id = event.object.message['peer_id']
            msg_id = event.object.message['id']
            text = event.object.message['text'].strip()
            from_id = event.object.message['from_id']
            chat_id = peer_id - 2000000000
            
            # Инициализируем пользователя если новый
            init_user(from_id)
            
            # Проверка мута и тишины для НЕ команд
            if not text.startswith('!'):
                if is_user_muted(peer_id, from_id):
                    kick_user(chat_id, from_id)
                    continue
                if str(peer_id) in silence_mode and silence_mode[str(peer_id)]:
                    if get_access(peer_id, from_id) < 30:
                        kick_user(chat_id, from_id)
                        continue
                continue
            
            # Убираем ! и получаем команду
            command_full = text[1:].strip().lower()
            if not command_full:
                continue
            
            parts = command_full.split()
            cmd = parts[0]
            args = " ".join(parts[1:]) if len(parts) > 1 else ""
            
            user_role = get_access(peer_id, from_id)
            
            print(f"⚡ Команда: {cmd}, аргументы: {args}, роль: {user_role}")
            
            # ========== ЭКОНОМИЧЕСКИЕ КОМАНДЫ ==========
            
            # !профиль
            if cmd == "профиль":
                role_num = get_access(peer_id, from_id)
                role_name = get_role_name(role_num)
                warns = user_data[str(from_id)].get("warns", 0)
                muted = "Да" if is_user_muted(peer_id, from_id) else "Нет"
                nick = user_data[str(from_id)].get("nickname", "")
                money = get_money(from_id)
                vip_status = "✅ Да" if is_vip(from_id) else "❌ Нет"
                vip_days = get_vip_days_left(from_id)
                vip_text = f" (осталось {vip_days} дн.)" if vip_days > 0 else ""
                nick_text = f"\n🏷️ Ник: {nick}" if nick else ""
                
                profile_text = f"""📊 **Ваш профиль**

⭐ Роль: {role_name} ({role_num})
⚠️ Варны: {warns}/3
🔇 Мут: {muted}{nick_text}
💰 Деньги: {money} монет
💎 VIP: {vip_status}{vip_text}"""
                send(peer_id, profile_text, msg_id)
                continue
            
            # !бонус
            if cmd == "бонус":
                if can_use_bonus(from_id):
                    bonus = random.randint(BONUS_RANGE[0], BONUS_RANGE[1])
                    
                    # Бонус для VIP беседы
                    if is_vip_chat(peer_id):
                        bonus = int(bonus * 1.2)
                        add_money(from_id, bonus)
                        send(peer_id, f"🎁 **Бонус получен!** (VIP беседа +20%)\n\n+{bonus} монет\n💰 Всего: {get_money(from_id)} монет\n\n⏰ Следующий бонус через 1 час.", msg_id)
                    else:
                        add_money(from_id, bonus)
                        send(peer_id, f"🎁 **Бонус получен!**\n\n+{bonus} монет\n💰 Всего: {get_money(from_id)} монет\n\n⏰ Следующий бонус через 1 час.", msg_id)
                    set_bonus_used(from_id)
                else:
                    last = last_bonus.get(str(from_id), 0)
                    remaining = 3600 - (time.time() - last)
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    send(peer_id, f"⏰ Бонус еще не доступен!\nПодождите {minutes} мин {seconds} сек.", msg_id)
                continue
            
            # !вип - меню покупки
            if cmd == "вип":
                vip_text = "💎 **Купить VIP статус**\n\n"
                for days, price in VIP_PRICES.items():
                    vip_text += f"🔹 VIP на {days} дн. — {price} монет\n"
                vip_text += f"\n💰 У вас: {get_money(from_id)} монет\n\n📝 Напишите: !купитьвип [дни]"
                send(peer_id, vip_text, msg_id)
                continue
            
            # !купитьвип
            if cmd == "купитьвип":
                if not args:
                    send(peer_id, "❌ Использование: !купитьвип [1/7/30]", msg_id)
                else:
                    try:
                        days = int(args.split()[0])
                        if days not in VIP_PRICES:
                            send(peer_id, "❌ Доступные дни: 1, 7, 30", msg_id)
                        else:
                            price = VIP_PRICES[days]
                            if remove_money(from_id, price):
                                set_vip(from_id, days)
                                send(peer_id, f"✅ Вы купили VIP на {days} дней!\n💰 Осталось: {get_money(from_id)} монет", msg_id)
                            else:
                                send(peer_id, f"❌ Недостаточно монет! Нужно: {price}, у вас: {get_money(from_id)}", msg_id)
                    except ValueError:
                        send(peer_id, "❌ Укажите количество дней (1, 7 или 30)", msg_id)
                continue
            
            # !перевод
            if cmd == "перевод":
                if not args:
                    send(peer_id, "❌ Использование: !перевод @user [сумма]", msg_id)
                else:
                    target = get_target_user(text, event)
                    if not target:
                        send(peer_id, "❌ Укажите пользователя (@ или ответом)", msg_id)
                    else:
                        try:
                            amount = int(args.split()[-1])
                            if amount <= 0:
                                send(peer_id, "❌ Сумма должна быть положительной", msg_id)
                            elif remove_money(from_id, amount):
                                add_money(target, amount)
                                send(peer_id, f"✅ Перевод выполнен!\n💰 {get_link(from_id)} перевел {amount} монет {get_link(target)}", msg_id)
                            else:
                                send(peer_id, f"❌ Недостаточно монет! У вас: {get_money(from_id)}", msg_id)
                        except ValueError:
                            send(peer_id, "❌ Укажите сумму числом", msg_id)
                continue
            
            # !пополнить (только владелец бота)
            if cmd == "пополнить" and from_id == BOT_OWNER_ID:
                if not args:
                    send(peer_id, "❌ Использование: !пополнить [сумма] или !пополнить @user [сумма]", msg_id)
                else:
                    target = get_target_user(text, event)
                    if target:
                        try:
                            amount = int(args.split()[-1])
                            add_money(target, amount)
                            send(peer_id, f"✅ {get_link(target)} пополнен на {amount} монет!\n💰 Теперь у него: {get_money(target)} монет", msg_id)
                        except ValueError:
                            send(peer_id, "❌ Укажите сумму числом", msg_id)
                    else:
                        try:
                            amount = int(args.split()[0])
                            add_money(from_id, amount)
                            send(peer_id, f"✅ Вы пополнили баланс на {amount} монет!\n💰 Теперь у вас: {get_money(from_id)} монет", msg_id)
                        except ValueError:
                            send(peer_id, "❌ Укажите сумму числом", msg_id)
                continue
            
            # !випбеседа (только владелец бота)
            if cmd == "випбеседа" and from_id == BOT_OWNER_ID:
                if is_vip_chat(peer_id):
                    set_vip_chat(peer_id, False)
                    send(peer_id, "🔓 VIP статус беседы **СНЯТ**!", msg_id)
                else:
                    set_vip_chat(peer_id, True)
                    send(peer_id, "🔒 **VIP статус беседы АКТИВИРОВАН!**\n\n💰 Бонусы в этой беседе увеличены на +20%", msg_id)
                continue
            
            # ========== ОСТАЛЬНЫЕ КОМАНДЫ ==========
            
            # !помощь
            if cmd == "помощь":
                help_text = f"""🤖 **Adrenaline Manager**

🔹 **Экономика:**
!профиль - Ваш профиль (деньги, VIP)
!бонус - Бонус раз в час
!вип - Меню покупки VIP
!купитьвип [1/7/30] - Купить VIP
!перевод @user [сумма] - Перевести деньги

🔹 **Все могут:**
!помощь - Это меню
!роли - Список ролей
!стафф - Сотрудники

🔹 **Роли 30+:**
!выдатьроль @user [число]
!снятьроль @user
!мут @user [минуты]
!снятьмут @user
!кик @user
!варн @user
!тишина

🔹 **Владелец беседы:**
!ник @user текст
!удалитьник @user
!списокников

🔹 **Владелец бота:**
!пополнить [сумма]
!пополнить @user [сумма]
!випбеседа"""
                send(peer_id, help_text, msg_id)
                continue
            
            # !роли
            if cmd == "роли":
                roles_text = "📋 **Список ролей:**\n\n"
                for role_num, role_name in ROLES.items():
                    roles_text += f"{role_name} — {role_num}\n"
                send(peer_id, roles_text, msg_id)
                continue
            
            # !стафф
            if cmd == "стафф" and user_role >= 30:
                staff_list = []
                for uid, udata in user_data.items():
                    if udata.get("role", 0) > 0:
                        role_num = udata.get("role", 0)
                        role_name = get_role_name(role_num)
                        staff_list.append(f"• {get_link(int(uid))} — {role_name} ({role_num})")
                if is_chat_owner(peer_id, from_id):
                    staff_list.insert(0, f"• {get_link(from_id)} — {get_role_name(100)} (100) - Владелец")
                if staff_list:
                    send(peer_id, "📋 **Стафф беседы:**\n\n" + "\n".join(staff_list), msg_id)
                else:
                    send(peer_id, "📋 Нет участников с ролями", msg_id)
                continue
            
            # !выдатьроль
            if cmd == "выдатьроль" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя (@)", msg_id)
                else:
                    parts_args = args.split()
                    if len(parts_args) < 1:
                        send(peer_id, "❌ !выдатьроль @user [число]", msg_id)
                    else:
                        try:
                            new_role = int(parts_args[-1])
                            if new_role not in ROLES:
                                send(peer_id, f"❌ Роль {new_role} не существует", msg_id)
                            elif not can_assign_role(user_role, new_role):
                                send(peer_id, f"❌ Нельзя выдать роль {new_role}", msg_id)
                            else:
                                if str(target) not in user_data:
                                    user_data[str(target)] = {"role": 0, "warns": 0}
                                user_data[str(target)]["role"] = new_role
                                save_data()
                                send(peer_id, f"✅ {get_link(target)} получил роль: {get_role_name(new_role)}", msg_id)
                        except ValueError:
                            send(peer_id, "❌ Укажите число роли", msg_id)
                continue
            
            # !снятьроль
            if cmd == "снятьроль" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if str(target) in user_data:
                        user_data[str(target)]["role"] = 0
                        save_data()
                        send(peer_id, f"✅ Роль {get_link(target)} сброшена", msg_id)
                    else:
                        send(peer_id, "❌ У пользователя нет роли", msg_id)
                continue
            
            # !ник
            if cmd == "ник" and user_role >= 100:
                parts_args = args.split(maxsplit=2)
                if len(parts_args) < 2:
                    send(peer_id, "❌ !ник @user Никнейм", msg_id)
                else:
                    target = get_target_user(text, event)
                    if not target:
                        send(peer_id, "❌ Укажите пользователя (@)", msg_id)
                    else:
                        new_nick = parts_args[1][:30]
                        if str(target) not in user_data:
                            user_data[str(target)] = {"role": 0, "warns": 0}
                        user_data[str(target)]["nickname"] = new_nick
                        save_data()
                        send(peer_id, f"✅ {get_link(target)} → ник: {new_nick}", msg_id)
                continue
            
            # !удалитьник
            if cmd == "удалитьник" and user_role >= 100:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if str(target) in user_data and "nickname" in user_data[str(target)]:
                        del user_data[str(target)]["nickname"]
                        save_data()
                        send(peer_id, f"✅ Ник {get_link(target)} удален", msg_id)
                    else:
                        send(peer_id, "❌ Нет ника", msg_id)
                continue
            
            # !списокников
            if cmd == "списокников" and user_role >= 100:
                nicks = []
                for uid, udata in user_data.items():
                    if udata.get("nickname"):
                        nicks.append(f"• {get_link(int(uid))} → {udata['nickname']}")
                if nicks:
                    send(peer_id, "📝 **Список ников:**\n\n" + "\n".join(nicks), msg_id)
                else:
                    send(peer_id, "📝 Ников нет", msg_id)
                continue
            
            # !варн
            if cmd == "варн" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if str(target) not in user_data:
                        user_data[str(target)] = {"role": 0, "warns": 0}
                    user_data[str(target)]["warns"] = user_data[str(target)].get("warns", 0) + 1
                    warns = user_data[str(target)]["warns"]
                    if warns >= 3:
                        if kick_user(chat_id, target):
                            send(peer_id, f"⚠️ {get_link(target)} кикнут за 3 варна!", msg_id)
                            if str(target) in user_data:
                                del user_data[str(target)]
                        else:
                            send(peer_id, "❌ Ошибка кика", msg_id)
                    else:
                        send(peer_id, f"⚠️ {get_link(target)} варн {warns}/3", msg_id)
                    save_data()
                continue
            
            # !мут
            if cmd == "мут" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    minutes = 5
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        minutes = int(numbers[0])
                    if minutes <= 0:
                        minutes = 1
                    if minutes > 10080:
                        minutes = 10080
                    mute_user(peer_id, target, minutes)
                    send(peer_id, f"🔇 {get_link(target)} замьючен на {minutes} мин!", msg_id)
                continue
            
            # !снятьмут
            if cmd == "снятьмут" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    unmute_user(peer_id, target)
                    send(peer_id, f"✅ {get_link(target)} размьючен", msg_id)
                continue
            
            # !кик
            if cmd == "кик" and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if kick_user(chat_id, target):
                        send(peer_id, f"🚪 {get_link(target)} кикнут!", msg_id)
                    else:
                        send(peer_id, "❌ Ошибка. Бот админ?", msg_id)
                continue
            
            # !тишина
            if cmd == "тишина" and user_role >= 30:
                if str(peer_id) not in silence_mode:
                    silence_mode[str(peer_id)] = False
                silence_mode[str(peer_id)] = not silence_mode[str(peer_id)]
                save_data()
                if silence_mode[str(peer_id)]:
                    send(peer_id, "🔇 **ТИШИНА ВКЛЮЧЕНА!**\nНе-админы будут кикаться.", msg_id)
                else:
                    send(peer_id, "🔈 **Тишина выключена**", msg_id)
                continue
                
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print("🔄 Переподключение через 5 секунд...")
        time.sleep(5)
        try:
            vk_session, vk, longpoll = create_session()
        except Exception as ex:
            print(f"❌ Не удалось переподключиться: {ex}")
