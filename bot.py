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

print(f"✅ Токен загружен: {GROUP_TOKEN[:20]}...")
print(f"✅ ID группы: {GROUP_ID}")
print(f"✅ Владелец: {BOT_OWNER_ID}")
# ===============================================

try:
    vk_session = vk_api.VkApi(token=GROUP_TOKEN)
    vk = vk_session.get_api()
    # Проверка токена
    vk.groups.getById(group_id=GROUP_ID)
    print("✅ Токен работает!")
except Exception as e:
    print(f"❌ Ошибка токена: {e}")
    exit(1)

longpoll = VkBotLongPoll(vk_session, GROUP_ID)
print("✅ LongPoll подключен!")

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
        params = {
            'peer_id': peer_id,
            'message': text,
            'random_id': random.randint(1, 2**31)
        }
        if reply_to:
            params['reply_to'] = reply_to
        vk.messages.send(**params)
        print(f"✅ Отправлено в {peer_id}: {text[:50]}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def is_vk_chat_admin(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_admin', False) or member.get('is_owner', False)
    except Exception as e:
        print(f"Ошибка проверки админа: {e}")
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

# ================= ВЕБ-СЕРВЕР =================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'VK Bot is running!')
    
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"🌐 Веб-сервер на порту {port}")
    server.serve_forever()

web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()

# ================= ОСНОВНОЙ ЦИКЛ =================
print("\n🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
print("📨 Ожидание сообщений...\n")

for event in longpoll.listen():
    print(f"📩 Событие: {event.type}")
    
    if event.type == VkBotEventType.MESSAGE_NEW:
        print(f"📝 От: {event.object.message['from_id']}")
        print(f"💬 Текст: {event.object.message['text']}")
        
        # Обработка только из бесед
        if event.from_chat:
            peer_id = event.object.message['peer_id']
            text = event.object.message['text'].strip()
            text_lower = text.lower()
            from_id = event.object.message['from_id']
            
            print(f"👥 Беседа ID: {peer_id}")
            print(f"👤 Пользователь: {from_id}")
            
            # Проверяем доступ
            access = get_access_level(peer_id, from_id)
            print(f"🔑 Уровень доступа: {access}")
            
            # ОТВЕЧАЕМ НА ЛЮБОЕ СООБЩЕНИЕ ДЛЯ ТЕСТА
            send(peer_id, f"✅ Привет! Твой ID: {from_id}. Уровень доступа: {access}. Напиши !помощь для команд.", 
                 reply_to=event.object.message['id'])
            
            # Обработка команд
            if text_lower == "!помощь":
                send(peer_id, "🤖 **Команды бота:**\n!профиль - твои данные\n!варн - выдать варн (админ)\n!мут - замутить (админ)\n!кик - кикнуть (админ)\n!тишина - режим тишины (админ)\n!ник - сменить название (владелец)", 
                     reply_to=event.object.message['id'])
            
            elif text_lower == "!профиль":
                if from_id not in user_data:
                    user_data[from_id] = {"role": 0, "warns": 0, "muted_until": 0}
                    save_all()
                role = "Админ" if user_data[from_id].get("role", 0) == 100 else "Пользователь"
                warns = user_data[from_id].get("warns", 0)
                send(peer_id, f"📊 Роль: {role}\n⚠️ Варны: {warns}/3", reply_to=event.object.message['id'])
            
            # Остальные команды добавьте по аналогии...
