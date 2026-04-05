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
    return {"users": {}, "silence_mode": False}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()
user_data = db["users"]
silence_mode = db.get("silence_mode", False)

def save_all():
    db["users"] = user_data
    db["silence_mode"] = silence_mode
    save_data(db)

def send(peer_id, text, reply_to=None):
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=text,
            random_id=random.randint(1, 2**31),
            reply_to=reply_to
        )
    except Exception as e:
        print(f"Ошибка: {e}")

def delete_message(peer_id, message_id):
    try:
        vk.messages.delete(
            message_ids=str(message_id),
            peer_id=peer_id,
            delete_for_all=1
        )
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
    if user_id in user_data and user_data[user_id].get("role") == 100:
        return 100
    if is_chat_admin(peer_id, user_id):
        return 100
    return 0

def is_muted(user_id):
    if user_id in user_data:
        if user_data[user_id].get("muted_until", 0) > time.time():
            return True
    return False

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

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue
    
    # Личные сообщения
    if event.from_user:
        try:
            vk.messages.send(
                user_id=event.object.message['from_id'],
                message="🤖 Я работаю только в беседах! Добавь меня в чат и дай права администратора.",
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
    
    # Проверка мута
    if is_muted(from_id):
        delete_message(peer_id, msg_id)
        continue
    
    # Проверка тишины
    if silence_mode:
        if get_access(peer_id, from_id) < 100:
            delete_message(peer_id, msg_id)
            continue
    
    # Только команды
    if not text_lower.startswith('!'):
        continue
    
    access = get_access(peer_id, from_id)
    is_owner = is_chat_owner(peer_id, from_id)
    
    # ========== КОМАНДЫ ==========
    
    # !помощь
    if text_lower == "!помощь":
        send(peer_id, """🤖 **Adrenaline Manager**

👑 **Админам:**
!мут @user [мин] - Замутить (сообщения удаляются)
!снятьмут @user - Снять мут
!кик @user - Кикнуть
!варн @user - Варн (3 варна = кик)
!тишина - Режим тишины
!роль @user 100 - Дать админку бота

🌟 **Владельцу беседы:**
!ник @user текст - Сменить ник
!удалитьник @user - Удалить ник
!списокников - Список ников""", msg_id)
    
    # !профиль
    elif text_lower == "!профиль":
        if from_id not in user_data:
            user_data[from_id] = {"role": 0, "warns": 0, "muted_until": 0}
            save_all()
        role = "👑 Админ" if user_data[from_id].get("role") == 100 else "👤 Юзер"
        warns = user_data[from_id].get("warns", 0)
        muted = "Да" if is_muted(from_id) else "Нет"
        nick = user_data[from_id].get("nickname")
        nick_text = f"\n🏷️ Ник: {nick}" if nick else ""
        send(peer_id, f"📊 **Профиль**\nРоль: {role}\nВарны: {warns}/3\nМут: {muted}{nick_text}", msg_id)
    
    # !ник (только владелец беседы)
    elif text_lower.startswith("!ник") and is_owner:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            send(peer_id, "❌ !ник @user Никнейм", msg_id)
        else:
            target = get_target_user(text, event)
            if not target:
                send(peer_id, "❌ Укажи пользователя (@)", msg_id)
            else:
                new_nick = parts[2][:30]
                if target not in user_data:
                    user_data[target] = {"role": 0, "warns": 0, "muted_until": 0}
                user_data[target]["nickname"] = new_nick
                save_all()
                send(peer_id, f"✅ {get_link(target)} → ник: {new_nick}", msg_id)
    
    # !удалитьник
    elif text_lower.startswith("!удалитьник") and is_owner:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажи пользователя", msg_id)
        elif target in user_data and "nickname" in user_data[target]:
            del user_data[target]["nickname"]
            save_all()
            send(peer_id, f"✅ Ник {get_link(target)} удален", msg_id)
        else:
            send(peer_id, "❌ У пользователя нет ника", msg_id)
    
    # !списокников
    elif text_lower == "!списокников" and is_owner:
        nicks = []
        for uid, data in user_data.items():
            if data.get("nickname"):
                nicks.append(f"• {get_link(uid)} → {data['nickname']}")
        if nicks:
            send(peer_id, "📝 **Список ников:**\n\n" + "\n".join(nicks), msg_id)
        else:
            send(peer_id, "📝 Ников нет. Используй !ник", msg_id)
    
    # !роль
    elif text_lower.startswith("!роль") and access >= 100:
        if from_id != BOT_OWNER_ID:
            send(peer_id, "❌ Только создатель бота", msg_id)
        else:
            target = get_target_user(text, event)
            if not target:
                send(peer_id, "❌ Укажи пользователя", msg_id)
            else:
                if target not in user_data:
                    user_data[target] = {"role": 0, "warns": 0, "muted_until": 0}
                user_data[target]["role"] = 100
                save_all()
                send(peer_id, f"✅ {get_link(target)} теперь админ бота", msg_id)
    
    # !варн
    elif text_lower.startswith("!варн") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажи пользователя", msg_id)
        else:
            if target not in user_data:
                user_data[target] = {"role": 0, "warns": 0, "muted_until": 0}
            user_data[target]["warns"] = user_data[target].get("warns", 0) + 1
            warns = user_data[target]["warns"]
            if warns >= 3:
                try:
                    vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                    send(peer_id, f"⚠️ {get_link(target)} кикнут за 3 варна!", msg_id)
                    del user_data[target]
                except:
                    send(peer_id, "❌ Ошибка кика. Бот админ?", msg_id)
            else:
                send(peer_id, f"⚠️ {get_link(target)} варн {warns}/3", msg_id)
            save_all()
    
    # !мут
    elif text_lower.startswith("!мут") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажи пользователя", msg_id)
        else:
            minutes = 5
            numbers = re.findall(r'\d+', text)
            if numbers:
                minutes = int(numbers[0])
            if minutes > 60:
                minutes = 60
            if target not in user_data:
                user_data[target] = {"role": 0, "warns": 0, "muted_until": 0}
            user_data[target]["muted_until"] = time.time() + (minutes * 60)
            save_all()
            send(peer_id, f"🔇 {get_link(target)} замьючен на {minutes} мин!", msg_id)
    
    # !снятьмут
    elif text_lower.startswith("!снятьмут") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажи пользователя", msg_id)
        elif target in user_data:
            user_data[target]["muted_until"] = 0
            save_all()
            send(peer_id, f"✅ {get_link(target)} размьючен", msg_id)
    
    # !кик
    elif text_lower.startswith("!кик") and access >= 100:
        target = get_target_user(text, event)
        if not target:
            send(peer_id, "❌ Укажи пользователя", msg_id)
        else:
            try:
                vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target)
                send(peer_id, f"🚪 {get_link(target)} кикнут!", msg_id)
            except:
                send(peer_id, "❌ Ошибка. Бот админ?", msg_id)
    
    # !тишина
    elif text_lower == "!тишина" and access >= 100:
        silence_mode = not silence_mode
        save_all()
        if silence_mode:
            send(peer_id, "🔇 **ТИШИНА ВКЛЮЧЕНА!**\nВсе сообщения не-админов будут удаляться.", msg_id)
        else:
            send(peer_id, "🔈 **Тишина выключена**", msg_id)
