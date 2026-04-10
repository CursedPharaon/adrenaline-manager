import sqlite3
import time

class BotDB:
    def __init__(self):
        self.conn = sqlite3.connect('game.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                money INTEGER DEFAULT 100,
                business TEXT DEFAULT 'Нет',
                house TEXT DEFAULT 'Нет',
                clothes TEXT DEFAULT 'Нет',
                clan TEXT DEFAULT 'Нет',
                job TEXT DEFAULT 'Безработный',
                last_bonus INTEGER DEFAULT 0,
                last_work INTEGER DEFAULT 0,
                last_mafia INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def reg_user(self, user_id):
        self.cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                "user_id": row[0], "money": row[1], "business": row[2],
                "house": row[3], "clothes": row[4], "clan": row[5],
                "job": row[6], "last_bonus": row[7], "last_work": row[8],
                "last_mafia": row[9]
            }
        return {"money": 0, "business": "Нет", "house": "Нет", "clothes": "Нет", 
                "clan": "Нет", "job": "Безработный"}

    def add_money(self, user_id, amount):
        self.reg_user(user_id)
        self.cursor.execute("UPDATE users SET money = money + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()
        return True

    def set_money(self, user_id, amount):
        self.reg_user(user_id)
        self.cursor.execute("UPDATE users SET money = ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    def transfer_money(self, from_id, to_id, amount):
        self.reg_user(from_id)
        self.reg_user(to_id)
        user = self.get_user(from_id)
        if user['money'] >= amount:
            self.add_money(from_id, -amount)
            self.add_money(to_id, amount)
            return True
        return False

    def buy_item(self, user_id, item_type, item_name):
        self.cursor.execute(f"UPDATE users SET {item_type} = ? WHERE user_id = ?", (item_name, user_id))
        self.conn.commit()

    def set_clan(self, user_id, clan_name):
        self.cursor.execute("UPDATE users SET clan = ? WHERE user_id = ?", (clan_name, user_id))
        self.conn.commit()

    def set_job(self, user_id, job_name):
        self.cursor.execute("UPDATE users SET job = ? WHERE user_id = ?", (job_name, user_id))
        self.conn.commit()

    def can_get_bonus(self, user_id):
        user = self.get_user(user_id)
        if time.time() - user['last_bonus'] > 86400:
            self.cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (int(time.time()), user_id))
            self.conn.commit()
            return True
        return False

    def can_work(self, user_id):
        user = self.get_user(user_id)
        if time.time() - user['last_work'] > 3600:
            self.cursor.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (int(time.time()), user_id))
            self.conn.commit()
            return True
        return False

    def can_mafia(self, user_id):
        user = self.get_user(user_id)
        if time.time() - user['last_mafia'] > 1800:
            self.cursor.execute("UPDATE users SET last_mafia = ? WHERE user_id = ?", (int(time.time()), user_id))
            self.conn.commit()
            return True
        return False

    def get_top(self, limit=10):
        self.cursor.execute("SELECT user_id, money FROM users ORDER BY money DESC LIMIT ?", (limit,))
        return self.cursor.fetchall()

    def get_clan_top(self, limit=5):
        self.cursor.execute("""
            SELECT clan, SUM(money) as total 
            FROM users 
            WHERE clan != 'Нет' 
            GROUP BY clan 
            ORDER BY total DESC 
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()