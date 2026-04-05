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

# Инициализация VK API
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
    params = {
        'peer_id': peer_id,
        'message': text,
        'random_id': random.randint(1, 2**31)
    }
    if reply_to:
        params['reply_to'] = reply_to
    vk.messages.send(**params)

def is_vk_chat_admin(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_admin', False) or member.get('is_owner', False)
    except:
        pass
    return False

def get_access_level(peer_id, user_id):
    if user_id == BOT_OWNER_ID:
        return 100
    if user_id in user_data and user_data[user_id].get("role", 0) == 100:
        return 100
    if is_vk_chat_admin(peer_id, user_id):
        return 100
    return 0

def is_muted(user_id):
    if user_id in user_data:
        if user_data[user_id].get("muted_until", 0) > time.time():
            return True
    return False

def extract_user_id(text, event):
    if event.object.message.get('reply_message'):
        return event.object.message['reply_message']['from_id']
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        return int(match.group(1))
    return None

# ================= ВЕБ-СЕРВЕР ДЛЯ RENDER =================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'VK Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Отключаем логи веб-сервера

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🌐 Веб-сервер запущен на порту {port}")
    server.serve_forever()

# Запускаем веб-сервер в отдельном потоке
web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()

# ================= ОСНОВНОЙ ЦИКЛ БОТА =================
print("🤖 VK Chat Manager запущен!")
print(f"📱 ID группы: {GROUP_ID}")
print(f"👑 Владелец: {BOT_OWNER_ID}")
print("✅ Бот готов к работе!")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW and event.from_chat:
        peer_id = event.object.message['peer_id']
        text = event.object.message['text'].strip()
        text_lower = text.lower()
        from_id = event.object.message['from_id']
        
        if silence_mode and get_access_level(peer_id, from_id) < 100:
            send(peer_id, "🔇 Режим тишины!", reply_to=event.object.message['id'])
            continue
        
        if is_muted(from_id):
            send(peer_id, "🔇 Вы замьючены!", reply_to=event.object.message['id'])
            continue
        
        access = get_access_level(peer_id, from_id)
        
        # ПОМОЩЬ
        if text_lower == "!помощь":
            help_text = """🤖 **VK Chat Manager**
            
👑 **Админ-команды:**
!варн @user - Выдать варн (3 варна = кик)
!мут @user 5 - Замутить на минут
!кик @user - Кикнуть из чата
!роль @user 100 - Выдать админку
!тишина - Режим тишины
!снятьмут @user - Снять мут

🌟 **Владелец бота:**
!ник Новое имя - Сменить название чата"""
            send(peer_id, help_text)
        
        # ПРОФИЛЬ
        elif text_lower == "!профиль":
            if from_id not in user_data:
                user_data[from_id] = {"role": 0, "warns": 0, "muted_until": 0}
                save_all()
            role = "Админ" if user_data[from_id].get("role", 0) == 100 else "Пользователь"
            warns = user_data[from_id].get("warns", 0)
            send(peer_id, f"📊 Роль: {role}\n⚠️ Варны: {warns}/3", reply_to=event.object.message['id'])
        
        # РОЛЬ
        elif text_lower.startswith("!роль") and access >= 100:
            target_id = extract_user_id(text, event)
            if target_id:
                if from_id != BOT_OWNER_ID:
                    send(peer_id, "❌ Только владелец бота может выдавать роль 100!")
                else:
                    if target_id not in user_data:
                        user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                    user_data[target_id]["role"] = 100
                    save_all()
                    send(peer_id, f"✅ [id{target_id}|Теперь админ бота]")
            else:
                send(peer_id, "❌ Ответьте на сообщение или используйте @")
        
        # ВАРН
        elif text_lower.startswith("!варн") and access >= 100:
            target_id = extract_user_id(text, event)
            if target_id:
                if target_id not in user_data:
                    user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                user_data[target_id]["warns"] += 1
                warns = user_data[target_id]["warns"]
                if warns >= 3:
                    try:
                        vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target_id)
                        send(peer_id, f"⚠️ [id{target_id}|Кикнут за 3 варна]")
                        if target_id in user_data:
                            del user_data[target_id]
                    except:
                        send(peer_id, "❌ Ошибка кика")
                else:
                    send(peer_id, f"⚠️ Варн {warns}/3 пользователю [id{target_id}|]")
                save_all()
            else:
                send(peer_id, "❌ Ответьте на сообщение")
        
        # МУТ
        elif text_lower.startswith("!мут") and access >= 100:
            target_id = extract_user_id(text, event)
            minutes = 5
            parts = text.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                minutes = int(parts[-1])
            if target_id:
                if target_id not in user_data:
                    user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                user_data[target_id]["muted_until"] = time.time() + (minutes * 60)
                save_all()
                send(peer_id, f"🔇 [id{target_id}|Замьючен на {minutes} мин]")
            else:
                send(peer_id, "❌ Ответьте на сообщение")
        
        # СНЯТЬ МУТ
        elif text_lower.startswith("!снятьмут") and access >= 100:
            target_id = extract_user_id(text, event)
            if target_id and target_id in user_data:
                user_data[target_id]["muted_until"] = 0
                save_all()
                send(peer_id, f"✅ [id{target_id}|Размьючен]")
        
        # КИК
        elif text_lower.startswith("!кик") and access >= 100:
            target_id = extract_user_id(text, event)
            if target_id:
                try:
                    vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target_id)
                    send(peer_id, f"🚪 [id{target_id}|Исключен]")
                except:
                    send(peer_id, "❌ Ошибка, бот не админ?")
            else:
                send(peer_id, "❌ Ответьте на сообщение")
        
        # ТИШИНА
        elif text_lower == "!тишина" and access >= 100:
            silence_mode = not silence_mode
            save_all()
            status = "включен" if silence_mode else "выключен"
            send(peer_id, f"🔇 Режим тишины {status}")
        
        # НИК (только владелец)
        elif text_lower.startswith("!ник") and from_id == BOT_OWNER_ID:
            new_title = text[4:].strip()
            if new_title:
                try:
                    vk.messages.editChat(chat_id=peer_id - 2000000000, title=new_title)
                    send(peer_id, f"✅ Название изменено на: {new_title}")
                except:
                    send(peer_id, "❌ Ошибка, бот не админ?")
            else:
                send(peer_id, "❌ Введите название после !ник")
