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

vk_session = vk_api.VkApi(token=GROUP_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# База данных
DATA_FILE = "bot_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}, "silence_mode": False, "muted_users": {}}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": user_data, "silence_mode": silence_mode, "muted_users": muted_users}, f, ensure_ascii=False, indent=2)

user_data = load_data()["users"]
silence_mode = load_data()["silence_mode"]
muted_users = load_data()["muted_users"]

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

def delete_message(peer_id, message_id):
    try:
        vk.messages.delete(
            message_ids=str(message_id),
            peer_id=peer_id,
            delete_for_all=1
        )
        return True
    except Exception as e:
        print(f"Ошибка удаления: {e}")
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
    if str(user_id) in user_data and user_data[str(user_id)].get("role") == 100:
        return 100
    if is_chat_admin(peer_id, user_id):
        return 100
    return 0

def is_user_muted(user_id):
    if str(user_id) in muted_users:
        if muted_users[str(user_id)] > time.time():
            return True
        else:
            del muted_users[str(user_id)]
            save_data()
    return False

def mute_user(user_id, minutes):
    muted_users[str(user_id)] = time.time() + (minutes * 60)
    save_data()

def unmute_user(user_id):
    if str(user_id) in muted_users:
        del muted_users[str(user_id)]
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

# Кэш для избежания дублирования
last_processed = {}
PROCESS_TIMEOUT = 3

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
    
    # ========== ПРОВЕРКА МУТА (УДАЛЯЕМ СООБЩЕНИЕ) ==========
    if is_user_muted(from_id):
        delete_message(peer_id, msg_id)
        continue
    
    # ========== ПРОВЕРКА ТИШИНЫ (УДАЛЯЕМ СООБЩЕНИЯ НЕ-АДМИНОВ) ==========
    if silence_mode:
        user_access = get_access(peer_id, from_id)
        if user_access < 100:
            delete_message(peer_id, msg_id)
            continue
    
    # Только команды с !
    if not text_lower.startswith('!'):
        continue
    
    access = get_access(peer_id, from_id)
    is_owner = is_chat_owner(peer_id, from_id)
    
    print(f"Команда: {text} от {from_id}, доступ: {access}")
    
    # ========== ОБРАБОТКА КОМАНД ==========
    
    # !помощь
    if text_lower == "!помощь":
        send(peer_id, """🤖 **Adrenaline Manager**

🔹 **Все могут:**
!помощь - Это сообщение
!профиль - Ваш профиль

🔹 **Админам (роль 100):**
!мут @user [мин] - Замутить
!снятьмут @user - Снять мут
!кик @user - Кикнуть
!варн @user - Варн (3 = кик)
!тишина - Вкл/выкл тишину

🔹 **Владельцу беседы:**
!ник @user текст - Сменить ник
!удалитьник @user - Удалить ник
!списокников - Список ников""", msg_id)
        continue
    
    # !профиль
    if text_lower == "!профиль":
        if str(from_id) not in user_data:
            user_data[str(from_id)] = {"role": 0, "warns": 0}
            save_data()
        role = "Админ" if user_data[str(from_id)].get("role") == 100 else "Пользователь"
        warns = user_data[str(from_id)].get("warns", 0)
        muted = "Да" if is_user_muted(from_id) else "Нет"
        nick = user_data[str(from_id)].get("nickname", "")
        nick_text = f"\n🏷️ Ник: {nick}" if nick else ""
        send(peer_id, f"📊 **Профиль**\nРоль: {role}\nВарны: {warns}/3\nМут: {muted}{nick_text}", msg_id)
        continue
    
    # !ник (только владелец)
    if text_lower.startswith("!ник") and is_owner:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            send(peer_id, "❌ Использование: !ник @user Никнейм", msg_id)
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
            send(peer_id, "❌ У пользователя нет ника", msg_id)
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
            send(peer_id, "📝 Ников нет. Используйте !ник", msg_id)
        continue
    
    # !роль (только владелец бота)
    if text_lower.startswith("!роль") and access >= 100:
        if from_id != BOT_OWNER_ID:
            send(peer_id, "❌ Только создатель бота", msg_id)
        else:
            target = get_target_user(text, event)
            if not target:
                send(peer_id, "❌ Укажите пользователя", msg_id)
            else:
                if str(target) not in user_data:
                    user_data[str(target)] = {"role": 0, "warns": 0}
                user_data[str(target)]["role"] = 100
                save_data()
                send(peer_id, f"✅ {get_link(target)} теперь админ бота", msg_id)
        continue
    
    # !варн
    if text_lower.startswith("!варн") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажите пользователя", msg_id)
        else:
            if str(target) not in user_data:
                user_data[str(target)] = {"role": 0, "warns": 0}
            user_data[str(target)]["warns"] = user_data[str(target)].get("warns", 0) + 1
            warns = user_data[str(target)]["warns"]
            if warns >= 3:
                try:
                    vk.messages.removeChatUser(chat_id=chat_id, user_id=target)
                    send(peer_id, f"⚠️ {get_link(target)} кикнут за 3 варна!", msg_id)
                    if str(target) in user_data:
                        del user_data[str(target)]
                except:
                    send(peer_id, "❌ Ошибка кика. Бот админ?", msg_id)
            else:
                send(peer_id, f"⚠️ {get_link(target)} варн {warns}/3", msg_id)
            save_data()
        continue
    
    # !мут
    if text_lower.startswith("!мут") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажите пользователя", msg_id)
        else:
            minutes = 5
            numbers = re.findall(r'\d+', text)
            if numbers:
                minutes = min(int(numbers[0]), 60)
            mute_user(target, minutes)
            send(peer_id, f"🔇 {get_link(target)} замьючен на {minutes} мин!", msg_id)
        continue
    
    # !снятьмут
    if text_lower.startswith("!снятьмут") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажите пользователя", msg_id)
        else:
            unmute_user(target)
            send(peer_id, f"✅ {get_link(target)} размьючен", msg_id)
        continue
    
    # !кик
    if text_lower.startswith("!кик") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажите пользователя", msg_id)
        else:
            try:
                vk.messages.removeChatUser(chat_id=chat_id, user_id=target)
                send(peer_id, f"🚪 {get_link(target)} кикнут!", msg_id)
            except:
                send(peer_id, "❌ Ошибка. Бот админ?", msg_id)
        continue
    
    # !тишина
    if text_lower == "!тишина" and access >= 100:
        silence_mode = not silence_mode
        save_data()
        if silence_mode:
            send(peer_id, "🔇 **ТИШИНА ВКЛЮЧЕНА!**\nВсе сообщения не-админов будут удаляться.", msg_id)
        else:
            send(peer_id, "🔈 **Тишина выключена**", msg_id)
        continue
