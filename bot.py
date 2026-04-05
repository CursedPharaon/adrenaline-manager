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
        params = {
            'peer_id': peer_id,
            'message': text,
            'random_id': random.randint(1, 2**31)
        }
        if reply_to:
            params['reply_to'] = reply_to
        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def is_vk_chat_admin(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_admin', False) or member.get('is_owner', False)
    except:
        pass
    return False

def is_vk_chat_owner(peer_id, user_id):
    try:
        members = vk.messages.getConversationMembers(peer_id=peer_id)
        for member in members['items']:
            if member['member_id'] == user_id:
                return member.get('is_owner', False)
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
        muted_until = user_data[user_id].get("muted_until", 0)
        if muted_until > time.time():
            return True
    return False

def extract_user_id(text, event):
    if event.object.message.get('reply_message'):
        return event.object.message['reply_message']['from_id']
    match = re.search(r'\[id(\d+)\|', text)
    if match:
        return int(match.group(1))
    return None

def get_nickname(user_id):
    if user_id in user_data and user_data[user_id].get("nickname"):
        return user_data[user_id]["nickname"]
    return None

def set_nickname(user_id, nick):
    if user_id not in user_data:
        user_data[user_id] = {"role": 0, "warns": 0, "muted_until": 0}
    user_data[user_id]["nickname"] = nick
    save_all()

def remove_nickname(user_id):
    if user_id in user_data and "nickname" in user_data[user_id]:
        del user_data[user_id]["nickname"]
        save_all()

def get_username(user_id):
    try:
        user_info = vk.users.get(user_ids=user_id, fields='screen_name')
        if user_info and user_info[0].get('screen_name'):
            return user_info[0]['screen_name']
    except:
        pass
    return None

def get_user_link(user_id):
    username = get_username(user_id)
    if username:
        return f"@{username}"
    else:
        return f"[id{user_id}|пользователь]"

# ================= ВЕБ-СЕРВЕР =================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Adrenaline Manager Bot is running!')
    
    def log_message(self, format, *args):
        pass

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

web_thread = threading.Thread(target=run_web_server, daemon=True)
web_thread.start()

# ================= ОСНОВНОЙ ЦИКЛ =================
print("🤖 Adrenaline Manager запущен!")
print(f"📱 ID группы: {GROUP_ID}")
print(f"👑 Владелец бота: {BOT_OWNER_ID}")
print("✅ Бот готов к работе!")

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        # ЛИЧНЫЕ СООБЩЕНИЯ
        if event.from_user:
            user_id = event.object.message['from_id']
            try:
                vk.messages.send(
                    user_id=user_id,
                    message="🤖 Привет! Я Adrenaline Manager. Я работаю только в беседах.\n\nДобавь меня в беседу, дай права администратора и напиши !помощь",
                    random_id=random.randint(1, 2**31)
                )
            except:
                pass
            continue
        
        # СООБЩЕНИЯ ИЗ БЕСЕД
        if event.from_chat:
            peer_id = event.object.message['peer_id']
            text = event.object.message['text'].strip()
            text_lower = text.lower()
            from_id = event.object.message['from_id']
            
            # ИГНОРИРУЕМ ВСЁ, КРОМЕ КОМАНД С !
            if not text_lower.startswith('!'):
                continue
            
            print(f"Команда: {text} от {from_id}")
            
            # Режим тишины (проверяем ТОЛЬКО для команд)
            if silence_mode:
                if get_access_level(peer_id, from_id) < 100:
                    send(peer_id, "🔇 Режим тишины! Команды доступны только администраторам.", reply_to=event.object.message['id'])
                    continue
            
            # Проверка мута (для команд тоже)
            if is_muted(from_id):
                send(peer_id, "🔇 Вы замьючены! Не можете использовать команды.", reply_to=event.object.message['id'])
                continue
            
            access = get_access_level(peer_id, from_id)
            is_owner = is_vk_chat_owner(peer_id, from_id)
            
            # ========== КОМАНДЫ ==========
            
            # ПОМОЩЬ
            if text_lower == "!помощь":
                help_text = """🤖 **Adrenaline Manager - Команды**

👑 **Админ-команды (роль 100):**
!варн @user - Выдать варн (3 варна = кик)
!мут @user [минуты] - Замутить (по умолчанию 5 мин)
!кик @user - Исключить из чата
!роль @user 100 - Выдать админку бота
!тишина - Вкл/выкл режим тишины
!снятьмут @user - Снять мут

🌟 **Владелец беседы ВК:**
!ник @user Новый ник - Сменить ник
!удалитьник @user - Удалить ник
!списокников - Показать все ники

📌 **Совет:** Ответьте на сообщение пользователя или используйте @"""
                send(peer_id, help_text)
            
            # ПРОФИЛЬ
            elif text_lower == "!профиль":
                if from_id not in user_data:
                    user_data[from_id] = {"role": 0, "warns": 0, "muted_until": 0}
                    save_all()
                role = "Админ бота" if user_data[from_id].get("role", 0) == 100 else "Пользователь"
                warns = user_data[from_id].get("warns", 0)
                muted = "Да" if is_muted(from_id) else "Нет"
                nick = get_nickname(from_id)
                nick_text = f"\n🏷️ Ник: {nick}" if nick else ""
                send(peer_id, f"📊 **Ваш профиль**\n⭐ Роль: {role}\n⚠️ Варны: {warns}/3\n🔇 Мут: {muted}{nick_text}", reply_to=event.object.message['id'])
            
            # НИК
            elif text_lower.startswith("!ник") and is_owner:
                parts = text.split(maxsplit=2)
                if len(parts) >= 3:
                    target_id = extract_user_id(text, event)
                    if not target_id:
                        send(peer_id, "❌ Укажите пользователя через @")
                    else:
                        new_nick = parts[2].strip()
                        if len(new_nick) > 30:
                            send(peer_id, "❌ Ник не длиннее 30 символов")
                        else:
                            set_nickname(target_id, new_nick)
                            send(peer_id, f"✅ {get_user_link(target_id)} → ник: **{new_nick}**")
                else:
                    send(peer_id, "❌ !ник @user НовыйНик")
            
            # УДАЛИТЬ НИК
            elif text_lower.startswith("!удалитьник") and is_owner:
                target_id = extract_user_id(text, event)
                if target_id:
                    remove_nickname(target_id)
                    send(peer_id, f"✅ Ник {get_user_link(target_id)} удален!")
                else:
                    send(peer_id, "❌ Укажите пользователя")
            
            # СПИСОК НИКОВ
            elif text_lower == "!списокников" and is_owner:
                nicks_list = []
                for uid, data in user_data.items():
                    if "nickname" in data:
                        nicks_list.append(f"• {get_user_link(uid)} → **{data['nickname']}**")
                
                if nicks_list:
                    result = "📝 **Список ников:**\n\n" + "\n".join(nicks_list)
                else:
                    result = "📝 Ников нет. Используй !ник @user Ник"
                send(peer_id, result)
            
            # РОЛЬ
            elif text_lower.startswith("!роль") and access >= 100:
                target_id = extract_user_id(text, event)
                if target_id:
                    if from_id != BOT_OWNER_ID:
                        send(peer_id, "❌ Только создатель бота!")
                    else:
                        if target_id not in user_data:
                            user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                        user_data[target_id]["role"] = 100
                        save_all()
                        send(peer_id, f"✅ {get_user_link(target_id)} теперь админ бота")
                else:
                    send(peer_id, "❌ Укажите пользователя")
            
            # ВАРН
            elif text_lower.startswith("!варн") and access >= 100:
                target_id = extract_user_id(text, event)
                if target_id:
                    if target_id not in user_data:
                        user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                    user_data[target_id]["warns"] = user_data[target_id].get("warns", 0) + 1
                    warns = user_data[target_id]["warns"]
                    
                    if warns >= 3:
                        try:
                            vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target_id)
                            send(peer_id, f"⚠️ {get_user_link(target_id)} кикнут за 3 варна!")
                            if target_id in user_data:
                                del user_data[target_id]
                        except:
                            send(peer_id, "❌ Ошибка кика. Бот админ?")
                    else:
                        send(peer_id, f"⚠️ {get_user_link(target_id)} варн {warns}/3")
                    save_all()
                else:
                    send(peer_id, "❌ Укажите пользователя")
            
            # МУТ - ИСПРАВЛЕН!
            elif text_lower.startswith("!мут") and access >= 100:
                target_id = extract_user_id(text, event)
                minutes = 5
                parts = text.split()
                # Ищем число в команде
                for part in parts:
                    if part.isdigit():
                        minutes = int(part)
                        break
                
                if target_id:
                    if target_id not in user_data:
                        user_data[target_id] = {"role": 0, "warns": 0, "muted_until": 0}
                    mute_time = time.time() + (minutes * 60)
                    user_data[target_id]["muted_until"] = mute_time
                    save_all()
                    send(peer_id, f"🔇 {get_user_link(target_id)} замьючен на {minutes} мин!")
                    print(f"Мут {target_id} на {minutes} мин до {mute_time}")
                else:
                    send(peer_id, "❌ Укажите пользователя: !мут @user 10")
            
            # СНЯТЬ МУТ
            elif text_lower.startswith("!снятьмут") and access >= 100:
                target_id = extract_user_id(text, event)
                if target_id:
                    if target_id in user_data:
                        user_data[target_id]["muted_until"] = 0
                        save_all()
                        send(peer_id, f"✅ {get_user_link(target_id)} размьючен!")
                else:
                    send(peer_id, "❌ Укажите пользователя")
            
            # КИК
            elif text_lower.startswith("!кик") and access >= 100:
                target_id = extract_user_id(text, event)
                if target_id:
                    try:
                        vk.messages.removeChatUser(chat_id=peer_id - 2000000000, user_id=target_id)
                        send(peer_id, f"🚪 {get_user_link(target_id)} исключен!")
                    except:
                        send(peer_id, "❌ Ошибка. Бот админ?")
                else:
                    send(peer_id, "❌ Укажите пользователя")
            
            # ТИШИНА - ИСПРАВЛЕНА!
            elif text_lower == "!тишина" and access >= 100:
                silence_mode = not silence_mode
                save_all()
                status = "ВКЛЮЧЕН 🔇" if silence_mode else "ВЫКЛЮЧЕН 🔈"
                send(peer_id, f"🔇 Режим тишины {status}")
                print(f"Режим тишины: {silence_mode}")
