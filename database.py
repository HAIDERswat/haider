import sqlite3
from datetime import datetime

def create_tables():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS services (
                    id TEXT PRIMARY KEY,
                    category TEXT,
                    name TEXT,
                    price REAL,
                    min_order INTEGER,
                    max_order INTEGER,
                    description TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_points (
                    user_id TEXT PRIMARY KEY,
                    points INTEGER
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    service_id TEXT,
                    quantity INTEGER,
                    status TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
                    user_id TEXT PRIMARY KEY
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_gifts (
                    user_id TEXT PRIMARY KEY,
                    last_gift_time TEXT
                 )''')
    conn.commit()
    conn.close()

def add_admin(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_admins():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in c.fetchall()]
    conn.close()
    return admins

def remove_admin(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_setting(key, value):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    value = c.fetchone()
    conn.close()
    return value[0] if value else None

def get_user_points(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT points FROM user_points WHERE user_id = ?", (user_id,))
    points = c.fetchone()
    conn.close()
    return points[0] if points else 0

def set_user_points(user_id, points):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)", (user_id, points))
    conn.commit()
    conn.close()

def add_user_order(user_id, order):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO user_orders (order_id, user_id, service_id, quantity, status) VALUES (?, ?, ?, ?, ?)",
              (order['order_id'], user_id, order['service_id'], order['quantity'], order['status']))
    conn.commit()
    conn.close()

def get_user_orders(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT order_id, service_id, quantity, status FROM user_orders WHERE user_id = ?", (user_id,))
    orders = [{'order_id': row[0], 'service': row[1], 'quantity': row[2], 'status': row[3]} for row in c.fetchall()]
    conn.close()
    return orders

def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM user_points")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_last_gift_time(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT last_gift_time FROM daily_gifts WHERE user_id = ?", (user_id,))
    last_gift_time = c.fetchone()
    conn.close()
    return datetime.fromisoformat(last_gift_time[0]) if last_gift_time else None

def set_last_gift_time(user_id, time):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO daily_gifts (user_id, last_gift_time) VALUES (?, ?)", (user_id, time.isoformat()))
    conn.commit()
    conn.close()
