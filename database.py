import sqlite3

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

# Add more database functions as needed
