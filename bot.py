import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import time
import re
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ================= КОНФИГУРАЦИЯ =================
GROUP_TOKEN = os.getenv("VK_TOKEN")
GROUP_ID = int(os.getenv("VK_GROUP_ID"))
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))

if not GROUP_TOKEN or not GROUP_ID or not BOT_OWNER_ID:
    print("❌ ОШИБКА: Не все переменные окружения заданы!")
    exit(1)
# ===============================================

# Глобальные переменные
vk_session = None
vk = None
longpoll = None

def init_vk():
    global vk_session, vk, longpoll
    vk_session = vk_api.VkApi(token=GROUP_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("✅ VK сессия инициализирована")

init_vk()

# База данных
DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}, "silence_mode": {}, "muted_users": {}}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": user_data, "silence_mode": silence_mode, "muted_users": muted_users}, f, ensure_ascii=False, indent=2)

data = load_data()
user_data = data["users"]
silence_mode = data.get("silence_mode", {})  # silence_mode привязан к peer_id
muted_users = data.get("muted_users", {})    # muted_users привязан к peer_id

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

def send(peer_id, text, reply_to=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=random.randint(1, 2**31),
            reply_to=reply_to
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def kick_user(chat_id, user_id):
    """Кикает пользователя из беседы"""
    try:
        vk.messages.removeChatUser(chat_id=chat_id, user_id=user_id)
        return True
    except Exception as e:
        print(f"Ошибка кика: {e}")
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
    """Получает уровень доступа пользователя"""
    if user_id == BOT_OWNER_ID:
        return 100
    if str(user_id) in user_data:
        return user_data[str(user_id)].get("role", 0)
    if is_chat_admin(peer_id, user_id):
        return 50
    return 0

def get_role_name(role):
    """Возвращает название роли по числу"""
    return ROLES.get(role, "👤 Пользователь")

def can_assign_role(giver_role, target_role):
    """Проверяет, может ли выдающий выдать роль"""
    if target_role >= giver_role:
        return False
    if target_role == 100:
        return False
    if giver_role < 30:
        return False
    return True

def is_user_muted(peer_id, user_id):
    """Проверяет, в муте ли пользователь в КОНКРЕТНОЙ беседе"""
    key = f"{peer_id}_{user_id}"
    if key in muted_users:
        if muted_users[key] > time.time():
            return True
        else:
            del muted_users[key]
            save_data()
    return False

def mute_user(peer_id, user_id, minutes):
    """Мутит пользователя в КОНКРЕТНОЙ беседе на N минут"""
    key = f"{peer_id}_{user_id}"
    muted_users[key] = time.time() + (minutes * 60)
    save_data()
    print(f"🔇 Пользователь {user_id} замьючен в беседе {peer_id} на {minutes} мин")

def unmute_user(peer_id, user_id):
    """Снимает мут в КОНКРЕТНОЙ беседе"""
    key = f"{peer_id}_{user_id}"
    if key in muted_users:
        del muted_users[key]
        save_data()
        print(f"✅ Пользователь {user_id} размьючен в беседе {peer_id}")

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
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def run_web():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ================= ОСНОВНОЙ ЦИКЛ =================
print("✅ Adrenaline Manager запущен!")
print(f"👑 Владелец бота: {BOT_OWNER_ID}")
print(f"📋 Система ролей: {ROLES}")

last_processed = {}
PROCESS_TIMEOUT = 3

while True:
    try:
        for event in longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue
            
            # Защита от дублирования
            event_id = f"{event.object.message['peer_id']}_{event.object.message['id']}"
            if event_id in last_processed and time.time() - last_processed[event_id] < PROCESS_TIMEOUT:
                continue
            last_processed[event_id] = time.time()
            
            # Личные сообщения
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
            
            # Сообщения из бесед
            if not event.from_chat:
                continue
            
            peer_id = event.object.message['peer_id']
            msg_id = event.object.message['id']
            text = event.object.message['text'].strip()
            text_lower = text.lower()
            from_id = event.object.message['from_id']
            chat_id = peer_id - 2000000000
            
            # ========== ПРОВЕРКА МУТА (КИК) - ТОЛЬКО ДЛЯ ЭТОЙ БЕСЕДЫ ==========
            if is_user_muted(peer_id, from_id):
                print(f"🔇 Мут {from_id} в беседе {peer_id} - кикаем")
                kick_user(chat_id, from_id)
                continue
            
            # ========== ПРОВЕРКА ТИШИНЫ (КИК) ==========
            if str(peer_id) in silence_mode and silence_mode[str(peer_id)]:
                user_access = get_access(peer_id, from_id)
                if user_access < 30:
                    print(f"🔇 Тишина в беседе {peer_id}! Кикаем {from_id}")
                    kick_user(chat_id, from_id)
                    continue
            
            # Только команды с !
            if not text_lower.startswith('!'):
                continue
            
            user_role = get_access(peer_id, from_id)
            is_owner = is_chat_owner(peer_id, from_id)
            
            print(f"⚡ Команда: {text}, роль: {user_role}, беседа: {peer_id}")
            
            # ========== КОМАНДЫ ==========
            
            # !помощь
            if text_lower == "!помощь":
                help_text = f"""🤖 **Adrenaline Manager**

🔹 **Все могут:**
!помощь - Это сообщение
!профиль - Ваш профиль
!роли - Список ролей

🔹 **Роли (30+ могут выдавать нижестоящие):**
{chr(10).join([f'  {v} — {k}' for k, v in ROLES.items()])}

🔹 **Команды для ролей 30+:**
!выдатьроль @user [число] - Выдать роль
!снятьроль @user - Снять роль
!мут @user [минуты] - Замутить (кик)
!снятьмут @user - Снять мут
!кик @user - Кикнуть
!варн @user - Варн (3 = кик)
!тишина - Вкл/выкл тишину (кик)

🔹 **Владельцу беседы:**
!ник @user текст - Сменить ник
!удалитьник @user - Удалить ник
!списокников - Список ников"""
                send(peer_id, help_text, msg_id)
                continue
            
            # !роли
            if text_lower == "!роли":
                roles_text = "📋 **Список ролей:**\n\n"
                for role_num, role_name in ROLES.items():
                    roles_text += f"{role_name} — {role_num}\n"
                send(peer_id, roles_text, msg_id)
                continue
            
            # !профиль
            if text_lower == "!профиль":
                if str(from_id) not in user_data:
                    user_data[str(from_id)] = {"role": 0, "warns": 0}
                    save_data()
                role_num = user_data[str(from_id)].get("role", 0)
                role_name = get_role_name(role_num)
                warns = user_data[str(from_id)].get("warns", 0)
                muted = "Да" if is_user_muted(peer_id, from_id) else "Нет"
                nick = user_data[str(from_id)].get("nickname", "")
                nick_text = f"\n🏷️ Ник: {nick}" if nick else ""
                send(peer_id, f"📊 **Профиль**\n⭐ Роль: {role_name} ({role_num})\n⚠️ Варны: {warns}/3\n🔇 Мут: {muted}{nick_text}", msg_id)
                continue
            
            # !выдатьроль
            if text_lower.startswith("!выдатьроль") and user_role >= 30:
                parts = text.split()
                if len(parts) < 3:
                    send(peer_id, "❌ !выдатьроль @user [0,10,20,30,50,80,100]", msg_id)
                else:
                    target = get_target_user(text, event)
                    if not target:
                        send(peer_id, "❌ Укажите пользователя (@)", msg_id)
                    else:
                        try:
                            new_role = int(parts[-1])
                            if new_role not in ROLES:
                                send(peer_id, f"❌ Роль {new_role} не существует! Доступны: {list(ROLES.keys())}", msg_id)
                            elif not can_assign_role(user_role, new_role):
                                send(peer_id, f"❌ Нельзя выдать роль {new_role} (выше вашей или нельзя выдавать)", msg_id)
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
            if text_lower.startswith("!снятьроль") and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if str(target) in user_data:
                        user_data[str(target)]["role"] = 0
                        save_data()
                        send(peer_id, f"✅ Роль {get_link(target)} сброшена до пользователя", msg_id)
                    else:
                        send(peer_id, "❌ У пользователя нет роли", msg_id)
                continue
            
            # !ник
            if text_lower.startswith("!ник") and is_owner:
                parts = text.split(maxsplit=2)
                if len(parts) < 3:
                    send(peer_id, "❌ !ник @user Никнейм", msg_id)
                else:
                    target = get_target_user(text, event)
                    if not target:
                        send(peer_id, "❌ Укажите пользователя (@)", msg_id)
                    else:
                        new_nick = parts[2][:30]
                        if str(target) not in user_data:
                            user_data[str(target)] = {"role": 0, "warns": 0}
                        user_data[str(target)]["nickname"] = new_nick
                        save_data()
                        send(peer_id, f"✅ {get_link(target)} → ник: {new_nick}", msg_id)
                continue
            
            # !удалитьник
            if text_lower.startswith("!удалитьник") and is_owner:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                elif str(target) in user_data and "nickname" in user_data[str(target)]:
                    del user_data[str(target)]["nickname"]
                    save_data()
                    send(peer_id, f"✅ Ник {get_link(target)} удален", msg_id)
                else:
                    send(peer_id, "❌ Нет ника", msg_id)
                continue
            
            # !списокников
            if text_lower == "!списокников" and is_owner:
                nicks = []
                for uid, data in user_data.items():
                    if data.get("nickname"):
                        nicks.append(f"• {get_link(int(uid))} → {data['nickname']}")
                if nicks:
                    send(peer_id, "📝 **Список ников:**\n\n" + "\n".join(nicks), msg_id)
                else:
                    send(peer_id, "📝 Ников нет", msg_id)
                continue
            
            # !варн
            if text_lower.startswith("!варн") and user_role >= 30:
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
            
            # !мут - ПРИВЯЗАН К КОНКРЕТНОЙ БЕСЕДЕ
            if text_lower.startswith("!мут") and user_role >= 30:
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
                        send(peer_id, f"⚠️ Максимальный мут - 7 дней. Установлено 7 дней.", msg_id)
                    mute_user(peer_id, target, minutes)
                    send(peer_id, f"🔇 {get_link(target)} замьючен в ЭТОЙ беседе на {minutes} мин! При попытке написать - кик.", msg_id)
                continue
            
            # !снятьмут - ПРИВЯЗАН К КОНКРЕТНОЙ БЕСЕДЕ
            if text_lower.startswith("!снятьмут") and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    unmute_user(peer_id, target)
                    send(peer_id, f"✅ {get_link(target)} размьючен в ЭТОЙ беседе", msg_id)
                continue
            
            # !кик
            if text_lower.startswith("!кик") and user_role >= 30:
                target = get_target_user(text, event)
                if not target:
                    send(peer_id, "❌ Укажите пользователя", msg_id)
                else:
                    if kick_user(chat_id, target):
                        send(peer_id, f"🚪 {get_link(target)} кикнут!", msg_id)
                    else:
                        send(peer_id, "❌ Ошибка. Бот админ?", msg_id)
                continue
            
            # !тишина - ПРИВЯЗАНА К КОНКРЕТНОЙ БЕСЕДЕ
            if text_lower == "!тишина" and user_role >= 30:
                if str(peer_id) not in silence_mode:
                    silence_mode[str(peer_id)] = False
                silence_mode[str(peer_id)] = not silence_mode[str(peer_id)]
                save_data()
                if silence_mode[str(peer_id)]:
                    send(peer_id, "🔇 **ТИШИНА ВКЛЮЧЕНА!**\nВсе, кто напишут (кроме ролей 30+), будут КИКНУТЫ!", msg_id)
                else:
                    send(peer_id, "🔈 **Тишина выключена**", msg_id)
                continue
                
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        print("🔄 Переподключение через 5 секунд...")
        time.sleep(5)
        try:
            init_vk()
        except:
            print("❌ Не удалось переподключиться")
