import telebot
import random
import time
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired, UserNotFound, ClientUnauthorizedError, FeedbackRequired
import threading
import sqlite3
from datetime import datetime, timedelta
import os
import logging
from queue import Queue
import requests
from requests.exceptions import ProxyError

# إعدادات تسجيل الدخول إلى إنستغرام والإعدادات الأخرى
INSTAGRAM_USERNAME = 'rjy.u'
INSTAGRAM_PASSWORD = 'haider123456@'
SESSION_FILE = 'insta_session.json'
OWN_USERNAME = 'rjy.u'

DATABASE_FILE = 'shared_bot_database.db'
PROXY_API_URL = 'https://proxy.webshare.io/api/v2/proxy/list/download/mgcreuafncsrkgfffmtjusbxkwsafayolabsogxu/EG/any/username/direct/-/'
proxies = []
operation_count = 0
sent_accounts_count = 0
check_limit = 10
unfollow_limit = 0

LOGGING_CHAT_ID = -4291371585
ADMIN_CHAT_ID = -1002178940580
NON_CONDITIONS_GROUP_CHAT_ID = -4263817165
FOLLOW_SUCCESS_CHAT_ID = -4282848741
TELEGRAM_TOKEN = '7134723898:AAEGBQ9arhKW4ewWdZjet2PCJBrSRxyAw9g'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

cl = Client()

# قائمة المتابعين المخزنة
following_accounts = []

# قفل لتجنب الوصول المتزامن لنفس الحساب
lock = threading.Lock()

# تهيئة متغيرات التشغيل المتعدد
bot_thread = None
running = False
paused = False
serial_number = 0
feedback_required = False
retry_queue = Queue()
follow_thread = None
follow_running = False
resume_checking = False
resume_following = False
unfollow_running = False

scheduled_unfollow_time = None
unfollow_timer_thread = None

# عداد عالمي لتتبع عدد العمليات
global_operation_count = 0

# محولات مخصصة لـ SQLite
def adapt_datetime(ts):
    return ts.isoformat()

def convert_datetime(ts):
    return datetime.fromisoformat(ts.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

def log_to_telegram(message):
    try:
        bot.send_message(LOGGING_CHAT_ID, message)
    except telebot.apihelper.ApiTelegramException as e:
        if e.result.status_code == 429:
            retry_after = int(e.result.json()['parameters']['retry_after'])
            print(f"⚠️ تجاوزت الحد الأقصى للطلبات. إعادة المحاولة بعد {retry_after} ثانية.")
            time.sleep(retry_after + 1)
            bot.send_message(LOGGING_CHAT_ID, message)
        elif e.result.status_code == 403:
            print("❌ البوت تم إزالته من المجموعة.")
        elif e.result.status_code == 401:
            print("❌ خطأ غير مصرح به: رمز البوت غير صالح أو تم إلغاؤه.")
        else:
            print(f"❌ خطأ غير متوقع: {e}")

def send_telegram_message(chat_id, text):
    try:
        bot.send_message(chat_id, text)
        time.sleep(random.uniform(1, 3))  # تأخير عشوائي بين 1-3 ثوانٍ
    except telebot.apihelper.ApiTelegramException as e:
        if e.result.status_code == 429:
            retry_after = int(e.result.json()['parameters']['retry_after'])
            print(f"⚠️ تجاوزت الحد الأقصى للطلبات. إعادة المحاولة بعد {retry_after} ثانية.")
            time.sleep(retry_after + 1)
            bot.send_message(chat_id, text)
        elif e.result.status_code == 403:
            print("❌ البوت تم إزالته من المجموعة.")
        else:
            print(f"❌ خطأ غير متوقع: {e}")

# أضف هذه الوظيفة هنا
def format_proxy(proxy):
    try:
        # تقسيم البروكسي إلى الأجزاء الخاصة به
        parts = proxy.split(':')
        if len(parts) == 4:
            ip = parts[0]
            port = parts[1]
            username = parts[2]
            password = parts[3]
            formatted_proxy = f"http://{username}:{password}@{ip}:{port}"
            return formatted_proxy
        else:
            log_to_telegram(f"⚠️ تنسيق البروكسي غير صحيح: {proxy}")
            return None
    except Exception as e:
        log_to_telegram(f"⚠️ خطأ في معالجة البروكسي: {proxy}, {e}")
        return None

# استبدل هذه الوظيفة بالنسخة المعدلة
def load_proxies_from_api():
    global proxies
    try:
        response = requests.get(PROXY_API_URL)
        if response.status_code == 200:
            raw_proxies = response.text.strip().split('\n')
            proxies = [format_proxy(proxy.strip()) for proxy in raw_proxies if format_proxy(proxy.strip())]
            if proxies:
                log_to_telegram("تم تحميل البروكسيات من الـ API بنجاح.")
            else:
                log_to_telegram("⚠️ لم يتم العثور على بروكسيات صالحة.")
        else:
            log_to_telegram(f"❌ حدث خطأ أثناء تحميل البروكسيات من الـ API: {response.status_code}")
            proxies = []
    except Exception as e:
        log_to_telegram(f"❌ حدث خطأ أثناء تحميل البروكسيات من الـ API: {e}")
        proxies = []

def connect_to_proxy():
    global cl, proxies, global_operation_count
    if proxies:
        for _ in range(len(proxies)):
            proxy = random.choice(proxies)
            print(f"Using proxy: {proxy}")  # طباعة البروكسي المستخدم للتصحيح
            try:
                cl.set_proxy(proxy)
                log_to_telegram(f"تم الاتصال بالبروكسي: {proxy}")
                global_operation_count = 0  # إعادة تعيين العداد بعد تغيير البروكسي
                return  # إذا نجح الاتصال، اخرج من الدالة
            except ValueError as ve:
                log_to_telegram(f"خطأ في تعيين البروكسي: {ve}")
            except requests.exceptions.ProxyError as e:
                log_to_telegram(f"خطأ في الاتصال عبر البروكسي: {e}")
        log_to_telegram("❌ فشل في الاتصال بجميع البروكسيات المتاحة.")
    else:
        log_to_telegram("❌ لا توجد بروكسيات متاحة للاستخدام.")

def switch_proxy_if_needed():
    global global_operation_count
    global_operation_count += 1
    if global_operation_count >= 5:  # تغيير البروكسي بعد كل 5 عمليات
        connect_to_proxy()

def save_session():
    cl.dump_settings(SESSION_FILE)
    log_to_telegram("✅ تم حفظ جلسة تسجيل الدخول.")

def load_session():
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
        log_to_telegram("✅ تم تحميل جلسة تسجيل الدخول المحفوظة.")
    else:
        log_to_telegram("⚠️ لا توجد جلسة محفوظة. سيتم تسجيل الدخول من جديد.")

def login_to_instagram():
    try:
        load_session()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        save_session()
    except Exception as e:
        log_to_telegram(f"❌ حدث خطأ أثناء تسجيل الدخول: {e}")
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
            log_to_telegram("🗑️ تم حذف الجلسة المحفوظة. المحاولة مرة أخرى...")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        save_session()

def get_db_connection():
    return sqlite3.connect(
        DATABASE_FILE, 
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, 
        check_same_thread=False
    )

def create_shared_tables():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                followed BOOLEAN,
                unfollowed BOOLEAN,
                conditions_met BOOLEAN,
                last_checked timestamp DEFAULT CURRENT_TIMESTAMP,
                last_sent timestamp,
                timestamp timestamp DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS serial_number (
                id INTEGER PRIMARY KEY,
                value INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_unfollows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schedule_time timestamp
            )
        ''')
        conn.commit()

def load_serial_number():
    global serial_number
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM serial_number WHERE id = 1')
        result = cursor.fetchone()
        if result:
            serial_number = result[0]
        else:
            cursor.execute('INSERT INTO serial_number (id, value) VALUES (1, 0)')
            conn.commit()
            serial_number = 0

def update_serial_number():
    global serial_number
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE serial_number SET value = ? WHERE id = 1', (serial_number,))
        conn.commit()

def reset_serial_number():
    global serial_number
    with get_db_connection() as conn:
        cursor = conn.cursor()
        serial_number = 0
        cursor.execute('UPDATE serial_number SET value = ?', (serial_number,))
        
        # إعادة تعيين الحقول المتعلقة بالمتابعة
        cursor.execute('''
            UPDATE processed_users 
            SET conditions_met = 0, followed = 0, unfollowed = 0, last_sent = NULL, last_checked = NULL 
            WHERE conditions_met = 1 OR followed = 1
        ''')
        
        conn.commit()
    log_to_telegram("✅ تم تصفير الرقم التسلسلي وإعادة تعيين الحسابات للمتابعة.")

def update_following_accounts():
    global following_accounts
    following_accounts = get_following_accounts(OWN_USERNAME)
    if following_accounts:
        log_to_telegram(f"✅ تم تحديث قائمة المتابعين لحساب {OWN_USERNAME}.")
    else:
        log_to_telegram(f"❌ حدث خطأ أثناء تحديث قائمة المتابعين لحساب {OWN_USERNAME}.")

def get_following_accounts(username):
    try:
        user_id = cl.user_id_from_username(username)
        following = cl.user_following(user_id)
        following_usernames = [user.username for user in following.values()]
        log_to_telegram(f"تم جلب قائمة المتابعين ({len(following_usernames)}) لحساب {username}.")
        return following_usernames
    except Exception as e:
        log_to_telegram(f"❌ حدث خطأ أثناء جلب قائمة المتابعين: {e}")
        return []

def check_following_conditions(user_id):
    global feedback_required
    global following_accounts  # استخدام قائمة المتابعين المخزنة
    
    try:
        user_info = cl.user_info(user_id)
        if user_info.is_private:
            return "private"
        following = cl.user_following(user_id)
        following_usernames = [user.username for user in following.values()]
        
        matched_accounts = [account for account in following_usernames if account in following_accounts]
        return len(matched_accounts) >= 10  # التحقق إذا كان المستخدم يتابع 10 حسابات على الأقل
    except FeedbackRequired:
        feedback_required = True
        log_to_telegram("❌ feedback_required: تم تقييد الأنشطة مؤقتًا. سيتم الانتظار قبل إعادة المحاولة.")
        return False
    except ClientUnauthorizedError:
        log_to_telegram("❌ الجلسة غير مصرح بها. إعادة المصادقة...")
        login_to_instagram()
        return False
    except ClientError as e:
        log_to_telegram(f"❌ حدث خطأ أثناء فحص متابعة المستخدم: {e}")
        return False

def save_or_update_account(user_id, username, profile_url, conditions_met):
    global serial_number
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # تحقق مما إذا كان المستخدم موجودًا بالفعل
        cursor.execute('SELECT 1 FROM processed_users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            # إذا كان المستخدم موجودًا، قم بتحديث الإدخال الموجود
            cursor.execute('''
                UPDATE processed_users
                SET username = ?, conditions_met = ?, last_checked = ?, last_sent = ?
                WHERE user_id = ?
            ''', (username, conditions_met, datetime.now(), datetime.now() if conditions_met else None, user_id))
        else:
            # إذا لم يكن المستخدم موجودًا، أدخل إدخالًا جديدًا
            cursor.execute('''
                INSERT INTO processed_users (user_id, username, followed, unfollowed, conditions_met, last_checked, last_sent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, False, False, conditions_met, datetime.now(), datetime.now() if conditions_met else None))
        
        conn.commit()

        if conditions_met:
            serial_number += 1
            update_serial_number()
            return serial_number
        return None

def can_process_or_send(user_id, within_last=48, check_reset=True):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_checked, last_sent FROM processed_users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            last_checked, last_sent = result
            now = datetime.now()
            if check_reset and last_sent and (now - last_sent) < timedelta(hours=within_last):
                return False, False
            if last_checked and (now - last_checked) < timedelta(hours=within_last):
                return False, False
    return True, True

def send_instagram_message(user_id, text):
    switch_proxy_if_needed()  # تبديل البروكسي إذا لزم الأمر
    try:
        cl.direct_send(text, [user_id])
        return "✅ تم إرسال الرسالة بنجاح"
    except Exception as e:
        return f"❌ حدث خطأ أثناء إرسال الرسالة: {e}"

def perform_random_activity_and_follow(user_id, username):
    global follow_running
    if not follow_running:
        return False
    
    try:
        switch_proxy_if_needed()  # تبديل البروكسي إذا لزم الأمر

        user_info = cl.user_info(user_id)
        if user_info.is_private:
            log_to_telegram(f"🔒 الحساب خاص: {username}. سيتم متابعة الحساب دون أي نشاط آخر.")
            cl.user_follow(user_id)
            send_instagram_message(user_id, 
                "تم إضافتك للدعم المجاني! 😍💕\n\n"
                "1️⃣ ضيف الحسابات الجديدة التي سنقوم باضافتها قريباً ورد الإضافة لكل من يضيفك. ✔️\n\n"
                "2️⃣ التقط صورة للإضافات التي ستحصل عليها، وانشرها كستوري مع وضع تاغ لي حتى أقوم بمشاركتها! 🙈💕\n\n"
                "شكراً لدعمك! 🌟"
            )
            return True
        
        user_medias = cl.user_medias(user_id, amount=10)
        if not user_medias:
            log_to_telegram(f"📂 لا توجد منشورات في حساب المستخدم: {username}. سيتم متابعة الحساب دون أي نشاط آخر.")
            cl.user_follow(user_id)
            send_instagram_message(user_id, 
                "تم إضافتك للدعم المجاني! 😍💕\n\n"
                "1️⃣ ضيف الحسابات الجديدة التي سنقوم باضافتها قريباً ورد الإضافة لكل من يضيفك. ✔️\n\n"
                "2️⃣ التقط صورة للإضافات التي ستحصل عليها، وانشرها كستوري مع وضع تاغ لي حتى أقوم بمشاركتها! 🙈💕\n\n"
                "شكراً لدعمك! 🌟"
            )
            return True
        
        media_id = random.choice(user_medias).id
        cl.media_like(media_id)
        log_to_telegram(f"👍 تم الإعجاب بمنشور المستخدم {username}")
        
        cl.user_follow(user_id)
        send_instagram_message(user_id, 
                "تم إضافتك للدعم المجاني! 😍💕\n\n"
                "1️⃣ ضيف الحسابات الجديدة التي سنقوم باضافتها قريباً ورد الإضافة لكل من يضيفك. ✔️\n\n"
                "2️⃣ التقط صورة للإضافات التي ستحصل عليها، وانشرها كستوري مع وضع تاغ لي حتى أقوم بمشاركتها! 🙈💕\n\n"
                "شكراً لدعمك! 🌟"
        )
        return True
        
    except FeedbackRequired as e:
        log_to_telegram(f"⚠️ إنستغرام طلب تأكيد الهوية أو تعطيل مؤقت: {e}")
        send_telegram_message(LOGGING_CHAT_ID, f"⚠️ حدث خطأ: إنستغرام طلب تأكيد الهوية أو تم تعطيل الحساب مؤقتًا أثناء محاولة متابعة {username}.")
        return False
    except ClientError as e:
        log_to_telegram(f"❌ حدث خطأ أثناء محاولة متابعة {username}: {e}")
        send_telegram_message(LOGGING_CHAT_ID, f"❌ حدث خطأ أثناء محاولة متابعة {username}: {e}")
        return False
    except Exception as e:
        log_to_telegram(f"❌ خطأ غير متوقع أثناء محاولة متابعة {username}: {e}")
        send_telegram_message(LOGGING_CHAT_ID, f"❌ خطأ غير متوقع أثناء محاولة متابعة {username}: {e}")
        return False

def follow_accounts(limit):
    global operation_count, serial_number, follow_running, resume_following
    followed_count = 0
    follow_running = True

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username 
            FROM processed_users 
            WHERE conditions_met = 1 
              AND followed = 0 
            ORDER BY id ASC
            LIMIT ?
        ''', (limit,))
        accounts_to_follow = cursor.fetchall()

    if not accounts_to_follow:
        log_to_telegram("🚫 لا يوجد حسابات جديدة لمتابعتها.")
        return

    for user_id, username in accounts_to_follow:
        if not follow_running:
            log_to_telegram("🛑 تم إيقاف عملية المتابعة.")
            break

        success = perform_random_activity_and_follow(user_id, username)
        if success:
            serial_number = save_or_update_account(user_id, username, f"https://www.instagram.com/{username}/", True)
            message = (
                f"#{serial_number} ✅ تم متابعة الحساب بنجاح:\n"
                f"👤 اسم المستخدم: {username}\n"
                f"🔗 الرابط: https://www.instagram.com/{username}/"
            )
            send_telegram_message(FOLLOW_SUCCESS_CHAT_ID, message)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE processed_users SET followed = 1, last_sent = ? WHERE user_id = ?', (datetime.now(), user_id))
                conn.commit()
            followed_count += 1
        else:
            message = f"❌ فشل في متابعة الحساب:\n👤 اسم المستخدم: {username}\n🔗 الرابط: https://www.instagram.com/{username}/"
            send_telegram_message(FOLLOW_SUCCESS_CHAT_ID, message)

        switch_proxy_if_needed()

        time.sleep(random.randint(60, 120))  # تأخير بين 60-120 ثوانٍ بين المتابعات

        if followed_count >= limit:
            break

    log_to_telegram(f"📊 تم متابعة {followed_count} حساب من أصل {limit} المطلوب.")
    follow_running = False
    if resume_following:
        follow_accounts(limit - followed_count)

def unfollow_accounts(limit=None):
    global feedback_required, unfollow_running, unfollow_limit

    unfollow_running = True
    unfollow_count = 0
    total_to_unfollow = get_unfollow_count()

    if limit is not None and limit < total_to_unfollow:
        total_to_unfollow = limit

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username 
            FROM processed_users 
            WHERE followed = 1 AND unfollowed = 0
            LIMIT ?
        ''', (total_to_unfollow,))
        accounts_to_unfollow = cursor.fetchall()

    for user_id, username in accounts_to_unfollow:
        if unfollow_count >= total_to_unfollow or not unfollow_running:
            break

        try:
            switch_proxy_if_needed()  # تبديل البروكسي إذا لزم الأمر

            cl.user_unfollow(user_id)
            log_to_telegram(f"🚫 تم إلغاء متابعة الحساب: {username}")
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE processed_users SET unfollowed = 1 WHERE user_id = ?', (user_id,))
                conn.commit()
            unfollow_count += 1

            unfollow_limit -= 1  # تحديث المتغير بعد كل عملية إلغاء متابعة
            send_start_stop_buttons(ADMIN_CHAT_ID)  # إعادة إرسال الأزرار مع العدد المحدث

        except FeedbackRequired as e:
            log_to_telegram(f"❌ حدث خطأ أثناء إلغاء متابعة الحساب {username}: {e}")
            feedback_required = True
            log_to_telegram("⚠️ تم تلقي خطأ 'feedback_required'. سيتم الانتظار لمدة 20 دقيقة قبل إعادة المحاولة.")
            time.sleep(1200)
            feedback_required = False
            return
        except Exception as e:
            log_to_telegram(f"❌ حدث خطأ أثناء إلغاء متابعة الحساب {username}: {e}")

        # تأخير طويل عشوائي بعد كل عملية إلغاء متابعة
        time.sleep(random.randint(120, 200))  # Delay between 120-200 seconds

    log_to_telegram(f"✅ تم إلغاء متابعة {unfollow_count} حساب من أصل {total_to_unfollow} المطلوب.")
    unfollow_running = False

def schedule_unfollow(hours):
    global scheduled_unfollow_time, unfollow_timer_thread

    def delayed_unfollow():
        global scheduled_unfollow_time
        time.sleep(hours * 3600)
        scheduled_unfollow_time = None
        unfollow_accounts()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        scheduled_unfollow_time = datetime.now() + timedelta(hours=hours)
        cursor.execute('INSERT INTO scheduled_unfollows (schedule_time) VALUES (?)', (scheduled_unfollow_time,))
        conn.commit()

    unfollow_timer_thread = threading.Thread(target=delayed_unfollow)
    unfollow_timer_thread.start()
    log_to_telegram(f"⏰ تم جدولة إلغاء المتابعة بعد {hours} ساعة.")

def show_remaining_unfollow_time(chat_id):
    if scheduled_unfollow_time:
        remaining_time = scheduled_unfollow_time - datetime.now()
        hours, remainder = divmod(int(remaining_time.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        bot.send_message(chat_id, f"⏳ الوقت المتبقي حتى إلغاء المتابعة: {hours} ساعة و {minutes} دقيقة و {seconds} ثانية.")
    else:
        bot.send_message(chat_id, "🚫 لا توجد عملية إلغاء متابعة مجدولة حالياً.")

def delete_scheduled_unfollow(chat_id):
    global scheduled_unfollow_time, unfollow_timer_thread

    if scheduled_unfollow_time:
        scheduled_unfollow_time = None
        if unfollow_timer_thread and unfollow_timer_thread.is_alive():
            unfollow_timer_thread.join(timeout=0.1)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM scheduled_unfollows')
            conn.commit()
        bot.send_message(chat_id, "❌ تم حذف عملية إلغاء المتابعة المجدولة.")
    else:
        bot.send_message(chat_id, "🚫 لا توجد عملية إلغاء متابعة مجدولة لحذفها.")

def retry_failed_accounts():
    while running:
        if not retry_queue.empty():
            user_id, username, profile_url = retry_queue.get()
            log_to_telegram(f"🔄 إعادة فحص الحساب: {username}")
            follow_status = check_following_conditions(user_id)
            if follow_status and follow_status != "private":
                serial_number = save_or_update_account(user_id, username, profile_url, True)
                if serial_number:
                    result_message = send_instagram_message(user_id, 
                        "🎉 مبروك! تم حجز اسمك للدعم المجاني لأنك طبقت الشروط بنجاح 🎉\n\n"
                        "📅 الدعم سيكون الساعة 9 مساءً بتوقيت العراق 🇮🇶\n"
                        "🕘 وهو ما يعادل:\n"
                        "🔸 الساعة 8 مساءً بتوقيت مصر 🇪🇬\n"
                        "🔸 الساعة 8 مساءً بتوقيت سوريا 🇸🇾\n"
                        "🔸 الساعة 9 مساءً بتوقيت السعودية 🇸🇦\n"
                        "🔸 الساعة 7 مساءً بتوقيت المغرب 🇲🇦\n"
                        "🔸 الساعة 9 مساءً بتوقيت اليمن 🇾🇪"
                    )
                    message = (
                        f"#{serial_number} ✅ تم التأكد من الحساب:\n"
                        f"👤 اسم المستخدم: {username}\n"
                        f"🔗 الرابط: {profile_url}\n"
                        f"{result_message}"
                    )
                    send_telegram_message(ADMIN_CHAT_ID, message)
            else:
                log_to_telegram(f"❌ لم ينجح الحساب في إعادة الفحص: {username}")
        time.sleep(1)

def process_messages_concurrently(folder):
    global check_limit, sent_accounts_count, operation_count, running, feedback_required

    try:
        threads = cl.direct_threads()
    except ClientError as e:
        log_to_telegram(f"❌ حدث خطأ أثناء محاولة جلب المحادثات: {e}. سيتم إيقاف البوت وإعادة تشغيله بعد دقيقة.")
        running = False
        time.sleep(60)  # انتظار لمدة دقيقة قبل إعادة التشغيل
        start_bot()
        return

    processed_users = 0

    for thread in threads:
        if not running:
            log_to_telegram("🛑 تم إيقاف عملية الفحص.")
            return
        if paused:
            time.sleep(1)
            continue

        for message in thread.messages:
            if not running:  # تأكد من التحقق من حالة التشغيل في كل خطوة
                log_to_telegram("🛑 تم إيقاف عملية الفحص.")
                return

            if sent_accounts_count >= check_limit:  # توقف الفحص عند الوصول إلى الحد المحدد
                log_to_telegram(f"✅ تم العثور على {check_limit} حسابات تطبق الشروط. تم إيقاف الفحص.")
                running = False
                return

            user_id = message.user_id
            process_single_message(user_id)

            time.sleep(1)  # إضافة تأخير بين كل طلب وآخر

    if feedback_required:
        log_to_telegram("⚠️ سيتم الانتظار 20 دقيقة قبل إعادة المحاولة بسبب قيود إنستغرام.")
        time.sleep(1200)
        feedback_required = False

    if sent_accounts_count >= check_limit:
        log_to_telegram("✅ تم الانتهاء من الفحص بنجاح.")
        running = False

def process_single_message(user_id):
    global operation_count, sent_accounts_count, running  # إضافة running هنا

    if not running:  # تحقق من حالة التشغيل في بداية العملية
        return

    with lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT conditions_met, followed FROM processed_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            if result:
                conditions_met, followed = result
                if conditions_met or followed:
                    return

            # تحقق إذا كان المستخدم قد تم تسجيله بأنه غير موجود
            cursor.execute('SELECT user_id FROM processed_users WHERE user_id = ? AND username IS NULL', (user_id,))
            not_found = cursor.fetchone()
            if not_found:
                return  # إذا كان المستخدم غير موجود سابقًا، تجاهله

        if not running:  # تحقق من حالة التشغيل بعد الوصول للمستخدم
            return

        try:
            user_info = cl.user_info(user_id)
            username = user_info.username
        except UserNotFound:
            log_to_telegram(f"❌ المستخدم ذو المعرف {user_id} غير موجود.")
            # تسجيل المستخدم في قاعدة البيانات بأنه غير موجود
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO processed_users (user_id, username, followed, unfollowed, conditions_met)
                    VALUES (?, NULL, 0, 0, 0)
                ''', (user_id,))
                conn.commit()
            return
        except ClientUnauthorizedError:
            log_to_telegram("❌ الجلسة غير مصرح بها. إعادة المصادقة...")
            login_to_instagram()
            return
        except Exception as e:
            log_to_telegram(f"❌ حدث خطأ غير متوقع: {e}")
            return

        if username == OWN_USERNAME:
            return

        can_process, can_send = can_process_or_send(user_id)

        if not can_process:
            return

        if not running:  # تحقق من حالة التشغيل قبل متابعة المستخدم
            return

        switch_proxy_if_needed()  # تبديل البروكسي إذا لزم الأمر

        follow_status = check_following_conditions(user_id)
        profile_url = f"https://www.instagram.com/{username}/"

        if follow_status == "private":
            result_message = send_instagram_message(user_id, "🔒 يرجى جعل حسابك عامًا حتى تتدخل في الدعم 🌟")
            message = f"🔒 الحساب خاص:\n👤 اسم المستخدم: {username}\n🔗 الرابط: {profile_url}\n{result_message}"
            save_or_update_account(user_id, username, profile_url, False)
            send_telegram_message(NON_CONDITIONS_GROUP_CHAT_ID, message)
        elif follow_status:
            serial_number = save_or_update_account(user_id, username, profile_url, True)
            if can_send and serial_number:
                result_message = send_instagram_message(user_id, 
                    "🎉 مبروك! تم حجز اسمك للدعم المجاني لأنك طبقت الشروط بنجاح 🎉\n\n"
                    "📅 الدعم سيكون الساعة 9 مساءً بتوقيت العراق 🇮🇶\n"
                    "🕘 وهو ما يعادل:\n"
                    "🔸 الساعة 8 مساءً بتوقيت مصر 🇪🇬\n"
                    "🔸 الساعة 8 مساءً بتوقيت سوريا 🇸🇾\n"
                    "🔸 الساعة 9 مساءً بتوقيت السعودية 🇸🇦\n"
                    "🔸 الساعة 7 مساءً بتوقيت المغرب 🇲🇦\n"
                    "🔸 الساعة 9 مساءً بتوقيت اليمن 🇾🇪"
                )
                message = (
                    f"#{serial_number} ✅ تم التأكد من الحساب:\n"
                    f"👤 اسم المستخدم: {username}\n"
                    f"🔗 الرابط: {profile_url}\n"
                    f"{result_message}"
                )
                send_telegram_message(ADMIN_CHAT_ID, message)
            sent_accounts_count += 1

            if sent_accounts_count >= check_limit:
                log_to_telegram(f"🛑 تم العثور على {check_limit} حسابات تطبق الشروط. تم إيقاف الفحص.")
                running = False
        else:
            save_or_update_account(user_id, username, profile_url, False)
            result_message = send_instagram_message(user_id, 
                "عذراً عزيزي، تم فحص حسابك ولكن لم تستوفِ الشروط.\n\n"
                "عليك إكمال الشروط لتتدخل في الدعم 🌟\n\n"
                "الشروط:\n"
                "1️⃣ أن تكون ضايف لكل من ضايفهم في هذا الحساب @rjy.u\n"
                "2️⃣ أن يكون حسابك عامًا وليس خاصًا 🔓\n\n"
                "بعد إتمام الشروط سيتم فحص حسابك مرة أخرى بعد 5 دقائق ⏰"
            )
            message = f"❌ الحساب لم يطبق الشروط:\n👤 اسم المستخدم: {username}\n🔗 الرابط: {profile_url}\n{result_message}"
            send_telegram_message(NON_CONDITIONS_GROUP_CHAT_ID, message)

            retry_queue.put((user_id, username, profile_url))

def check_without_message(limit):
    global sent_accounts_count, running

    running = True
    sent_accounts_count = 0

    def check_process():
        global running, sent_accounts_count  # إضافة global هنا
        while running and sent_accounts_count < limit:
            process_messages_concurrently('general')
            process_messages_concurrently('primary')
            time.sleep(1)  # تأخير بسيط لتجنب التحميل الزائد على السيرفر

        log_to_telegram(f"✅ تم الوصول إلى الحد الأقصى للحسابات المستوفية للشروط ({limit}). تم إيقاف الفحص.")
        running = False

    check_thread = threading.Thread(target=check_process)
    check_thread.start()

def run_bot():
    global running, resume_checking
    while running:
        try:
            process_messages_concurrently('general')
            if not running:
                break
            process_messages_concurrently('primary')
            if not running:
                break
        except ProxyError as e:
            log_to_telegram(f"❌ فشل الاتصال بجميع البروكسيات. إعادة تشغيل البوت بعد 60 ثانية.")
            running = False
            time.sleep(60)
            start_bot()
        except sqlite3.OperationalError as e:
            if "disk is full" in str(e):
                log_to_telegram("❌ خطأ: القرص أو قاعدة البيانات ممتلئة.")
                running = False
                cleanup_old_data()  # تنظيف البيانات القديمة لتوفير مساحة
                time.sleep(60)  # انتظر 60 ثانية قبل المحاولة مرة أخرى
                start_bot()
        except Exception as e:
            log_to_telegram(f"❌ Unexpected error in run_bot: {e}")
    if resume_checking:
        start_bot()

def start_bot():
    global running, paused, bot_thread, resume_checking, resume_following

    if bot_thread and bot_thread.is_alive():
        log_to_telegram("⚠️ البوت يعمل بالفعل. لا يمكن بدء عملية جديدة.")
        return

    running = True
    paused = False
    resume_checking = False
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    retry_thread = threading.Thread(target=retry_failed_accounts)
    retry_thread.start()

def stop_following():
    global follow_running, resume_following
    follow_running = False
    resume_following = False

def stop_unfollowing():
    global unfollow_running
    unfollow_running = False

def get_unfollow_count():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM processed_users WHERE followed = 1 AND unfollowed = 0')
        count = cursor.fetchone()[0]
    return count

def send_start_stop_buttons(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()

    start_button = telebot.types.InlineKeyboardButton("🟢 بدء الفحص", callback_data="start_checking")
    stop_button = telebot.types.InlineKeyboardButton("🔴 إيقاف الفحص", callback_data="stop_checking")
    resume_check_button = telebot.types.InlineKeyboardButton("🔄 استئناف الفحص", callback_data="resume_checking")
    resume_follow_button = telebot.types.InlineKeyboardButton("🔄 استئناف المتابعة", callback_data="resume_following")
    update_following_button = telebot.types.InlineKeyboardButton("🔄 تحديث قائمة المتابعين", callback_data="update_following")
    change_limit_button = telebot.types.InlineKeyboardButton("📝 تعيين عدد الحسابات", callback_data="change_check_limit")
    reset_serial_button = telebot.types.InlineKeyboardButton("🔄 تصفير الرقم التسلسلي", callback_data="reset_serial_number")
    follow_button = telebot.types.InlineKeyboardButton("👥 متابعة الحسابات المستوفية", callback_data="follow_accounts")
    stop_follow_button = telebot.types.InlineKeyboardButton("🛑 إيقاف المتابعة", callback_data="stop_following")
    show_count_button = telebot.types.InlineKeyboardButton("📊 عرض عدد الحسابات", callback_data="show_accounts_count")
    unfollow_button = telebot.types.InlineKeyboardButton("🚫 إلغاء المتابعة", callback_data="unfollow_accounts")
    schedule_unfollow_button = telebot.types.InlineKeyboardButton("⏰ جدولة إلغاء المتابعة", callback_data="schedule_unfollow")
    show_remaining_time_button = telebot.types.InlineKeyboardButton("⏳ عرض الوقت المتبقي", callback_data="show_remaining_time")
    delete_scheduled_unfollow_button = telebot.types.InlineKeyboardButton("❌ حذف جدولة إلغاء المتابعة", callback_data="delete_scheduled_unfollow")
    check_without_message_button = telebot.types.InlineKeyboardButton("🔍 فحص بدون رسالة", callback_data="check_without_message")  
    unfollow_count_button = telebot.types.InlineKeyboardButton("🚫 عرض الحسابات المتاحة للالغاء المتابعة", callback_data="show_unfollow_count")
    set_unfollow_limit_button = telebot.types.InlineKeyboardButton(f"📝 تعيين عدد حسابات الإلغاء ({get_unfollow_count()})", callback_data="set_unfollow_limit")
    stop_unfollow_button = telebot.types.InlineKeyboardButton("🛑 إيقاف إلغاء المتابعة", callback_data="stop_unfollowing")

    # Add other existing buttons here as needed
    markup.add(start_button)
    markup.add(stop_button)
    markup.add(resume_check_button)
    markup.add(resume_follow_button)
    markup.add(update_following_button)
    markup.add(change_limit_button)
    markup.add(reset_serial_button)
    markup.add(follow_button)
    markup.add(stop_follow_button)
    markup.add(show_count_button)
    markup.add(unfollow_button)
    markup.add(schedule_unfollow_button)
    markup.add(show_remaining_time_button)
    markup.add(delete_scheduled_unfollow_button)
    markup.add(check_without_message_button)
    markup.add(unfollow_count_button)
    markup.add(set_unfollow_limit_button)
    markup.add(stop_unfollow_button)

    bot.send_message(chat_id, "اختر إجراءً:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global running, paused, resume_checking, resume_following

    if call.data == "start_checking":
        start_bot()
        bot.send_message(call.message.chat.id, f"تم تشغيل البوت مع حد الفحص: {check_limit}.")
    elif call.data == "stop_checking":
        running = False
        paused = False
        bot.send_message(call.message.chat.id, "🛑 تم إيقاف عملية الفحص على الفور.")
    elif call.data == "resume_checking":
        resume_checking = True
        start_bot()
        bot.send_message(call.message.chat.id, "🔄 تم استئناف عملية الفحص.")
    elif call.data == "resume_following":
        resume_following = True
        bot.send_message(call.message.chat.id, "يرجى إرسال عدد الحسابات التي ترغب في متابعتها:")
        bot.register_next_step_handler(call.message, set_follow_limit)
    elif call.data == "change_check_limit":
        bot.send_message(call.message.chat.id, "يرجى إرسال عدد الحسابات التي ترغب في فحصها:")
        bot.register_next_step_handler(call.message, set_check_limit)
    elif call.data == "reset_serial_number":
        reset_serial_number()
        bot.send_message(call.message.chat.id, "تم تصفير الرقم التسلسلي للحسابات التي استوفت الشروط.")
    elif call.data == "follow_accounts":
        bot.send_message(call.message.chat.id, "يرجى إرسال عدد الحسابات التي ترغب في متابعتها:")
        bot.register_next_step_handler(call.message, set_follow_limit)
    elif call.data == "stop_following":
        stop_following()
        bot.send_message(call.message.chat.id, "تم إيقاف عملية المتابعة.")
    elif call.data == "show_accounts_count":
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM processed_users WHERE conditions_met = 1')
            count = cursor.fetchone()[0]
        bot.send_message(call.message.chat.id, f"عدد الحسابات التي طبقت الشروط: {count}")
    elif call.data == "unfollow_accounts":
        unfollow_accounts()
        bot.send_message(call.message.chat.id, "تم إلغاء متابعة الحسابات التي تم متابعتها.")
    elif call.data == "schedule_unfollow":
        bot.send_message(call.message.chat.id, "يرجى إرسال عدد الساعات لجدولة إلغاء المتابعة:")
        bot.register_next_step_handler(call.message, set_unfollow_schedule)
    elif call.data == "show_remaining_time":
        show_remaining_unfollow_time(call.message.chat.id)
    elif call.data == "delete_scheduled_unfollow":
        delete_scheduled_unfollow(call.message.chat.id)
    elif call.data == "update_following":
        update_following_accounts()
        bot.send_message(call.message.chat.id, "تم تحديث قائمة المتابعين.")
    elif call.data == "check_without_message":  
        bot.send_message(call.message.chat.id, "يرجى إرسال الحد الأقصى للحسابات المستوفية للشروط:")
        bot.register_next_step_handler(call.message, set_check_without_message_limit)
    elif call.data == "show_unfollow_count":
        count = get_unfollow_count()
        bot.send_message(call.message.chat.id, f"🚫 عدد الحسابات المتاحة لإلغاء المتابعة: {count}")
    elif call.data == "set_unfollow_limit":
        bot.send_message(call.message.chat.id, f"يرجى إرسال عدد الحسابات التي ترغب في إلغاء متابعتها:")
        bot.register_next_step_handler(call.message, set_unfollow_limit)
    elif call.data == "stop_unfollowing":
        stop_unfollowing()
        bot.send_message(call.message.chat.id, "🛑 تم إيقاف عملية إلغاء المتابعة.")

def set_check_limit(message):
    global check_limit
    try:
        limit = int(message.text)
        if limit > 0:
            check_limit = limit
            bot.send_message(message.chat.id, f"تم ضبط حد الفحص إلى {check_limit}.")
        else:
            bot.send_message(message.chat.id, "يرجى إدخال رقم موجب.")
    except ValueError:
        bot.send_message(message.chat.id, "رقم غير صالح. حاول مرة أخرى.")

def set_follow_limit(message):
    try:
        limit = int(message.text)
        if limit > 0:
            bot.send_message(message.chat.id, f"سيتم متابعة {limit} حساب.")
            global follow_thread
            follow_thread = threading.Thread(target=follow_accounts, args=(limit,))
            follow_thread.start()
        else:
            bot.send_message(message.chat.id, "يرجى إدخال رقم موجب.")
    except ValueError:
        bot.send_message(message.chat.id, "رقم غير صالح. حاول مرة أخرى.")

def set_unfollow_schedule(message):
    try:
        hours = int(message.text)
        if hours > 0:
            schedule_unfollow(hours)
            bot.send_message(message.chat.id, f"تم جدولة إلغاء المتابعة بعد {hours} ساعة.")
        else:
            bot.send_message(message.chat.id, "يرجى إدخال عدد ساعات موجب.")
    except ValueError:
        bot.send_message(message.chat.id, "رقم غير صالح. حاول مرة أخرى.")

def set_check_without_message_limit(message):
    try:
        limit = int(message.text)
        if limit > 0:
            bot.send_message(message.chat.id, f"سيتم فحص {limit} حسابات بدون إرسال رسالة للمستخدمين.")
            check_without_message(limit)
        else:
            bot.send_message(message.chat.id, "يرجى إدخال رقم موجب.")
    except ValueError:
        bot.send_message(message.chat.id, "رقم غير صالح. حاول مرة أخرى.")

def set_unfollow_limit(message):
    global unfollow_limit
    try:
        limit = int(message.text)
        if limit > 0:
            unfollow_limit = limit
            bot.send_message(message.chat.id, f"سيتم إلغاء متابعة {limit} حساب.")
            unfollow_accounts(limit)
        else:
            bot.send_message(message.chat.id, "يرجى إدخال رقم موجب.")
    except ValueError:
        bot.send_message(message.chat.id, "رقم غير صالح. حاول مرة أخرى.")

def cleanup_old_data():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # حذف السجلات الأقدم من 30 يومًا كمثال
        cursor.execute('DELETE FROM processed_users WHERE last_checked < ?', (datetime.now() - timedelta(days=30),))
        conn.commit()
    log_to_telegram("✅ تم تنظيف البيانات القديمة من قاعدة البيانات.")

def run_polling():
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except requests.exceptions.ConnectionError as e:
            log_to_telegram(f"⚠️ فقد الاتصال بالخادم: {e}. إعادة المحاولة بعد 15 ثانية.")
            time.sleep(15)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 502:
                log_to_telegram(f"⚠️ خطأ 502 Bad Gateway: {e}. إعادة المحاولة بعد 30 ثانية.")
                time.sleep(30)
            else:
                log_to_telegram(f"❌ حدث خطأ غير متوقع: {e}. إعادة المحاولة بعد 15 ثانية.")
                time.sleep(15)
        except Exception as e:
            log_to_telegram(f"❌ حدث خطأ غير متوقع: {e}. إعادة المحاولة بعد 15 ثانية.")
            time.sleep(15)

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    send_start_stop_buttons(message.chat.id)

if __name__ == "__main__":
    create_shared_tables()
    load_serial_number()
    load_proxies_from_api()
    connect_to_proxy()
    login_to_instagram()

    run_polling()
