import requests
import shelve
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.ext import ConversationHandler
from datetime import datetime, timedelta

# استخدام shelve لتخزين البيانات بشكل دائم
with shelve.open("bot_data") as db:
    if "services" not in db:
        db["services"] = {
            'instagram': {},
            'telegram': {},
            'tiktok': {},
            'facebook': {},
            'youtube': {}
        }
    services = db["services"]
    
    if "user_points" not in db:
        db["user_points"] = {}
    user_points = db["user_points"]
    
    if "user_orders" not in db:
        db["user_orders"] = {}
    user_orders = db["user_orders"]
    
    if "gift_points" not in db:
        db["gift_points"] = 10
    gift_points = db["gift_points"]
    
    if "daily_gift_points" not in db:
        db["daily_gift_points"] = 10
    daily_gift_points = db["daily_gift_points"]
    
    if "referral_points" not in db:
        db["referral_points"] = 5
    referral_points = db["referral_points"]
    
    if "user_daily_gift" not in db:
        db["user_daily_gift"] = {}
    user_daily_gift = db["user_daily_gift"]
    
    if "user_joined_channels" not in db:
        db["user_joined_channels"] = {}
    user_joined_channels = db["user_joined_channels"]
    
    if "admins" not in db:
        db["admins"] = [6726412293]  # ضع معرف الإدمن هنا
    admins = db["admins"]
    
    if "charge_description" not in db:
        db["charge_description"] = "لشحن النقاط، يرجى الضغط على الرابط التالي:"
    charge_description = db["charge_description"]
    
    if "API_BASE_URL" not in db:
        db["API_BASE_URL"] = "https://peakerr.com/api/v2"
    API_BASE_URL = db["API_BASE_URL"]
    
    if "API_KEY" not in db:
        db["API_KEY"] = "0d062fe0a9a42280c59cdab4166fbf92"
    API_KEY = db["API_KEY"]

# تعريف الحالات لـ ConversationHandler
STATES = {
    'NAME': 0,
    'ID': 1,
    'PRICE': 2,
    'MIN': 3,
    'MAX': 4,
    'DESCRIPTION': 5,
    'SELECT_CATEGORY': 6,
    'ADD_SERVICE': 7,
    'SELECT_SERVICE': 8,
    'QUANTITY': 9,
    'LINK': 10,
    'CONFIRM': 11,
    'ADD_POINTS_USER': 12,
    'ADD_POINTS_AMOUNT': 13,
    'SET_GIFT_POINTS': 14,
    'DEDUCT_POINTS_USER': 15,
    'DEDUCT_POINTS_AMOUNT': 16,
    'TRACK_ORDER': 17,
    'SET_ADMIN_USER': 18,
    'REMOVE_ADMIN_USER': 19,
    'SET_DESCRIPTION': 20,
    'SET_API_DETAILS': 21
}

CATEGORY_MAP = {
    'خدمات_إنستا': 'instagram',
    'خدمات_تليجرام': 'telegram',
    'خدمات_تيك_توك': 'tiktok',
    'خدمات_فيسبوك': 'facebook',
    'خدمات_يوتيوب': 'youtube'
}

async def ابدأ(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # تحقق من وجود معرف المستخدم المحيل في الرسالة
    if context.args:
        referrer_id = context.args[0]
        if referrer_id != str(user_id):  # تأكد من أن المستخدم الجديد ليس نفس الشخص الذي شارك الرابط
            referrer_points = user_points.get(referrer_id, 0)
            user_points[referrer_id] = referrer_points + referral_points  # إضافة نقاط للمستخدم المحيل
            with shelve.open("bot_data") as db:
                db["user_points"] = user_points
            await update.message.reply_text(f"لقد انضممت عبر رابط إحالة! تم إضافة {referral_points} نقاط للمستخدم الذي أحالك.")

    points = user_points.get(str(user_id), 0)

    معلومات_النص = (
        f"🆔 المعرف: {user_id}\n"
        f"👤 اسم المستخدم: @{username}\n"
        f"💸 النقاط: {points}\n\n"
    )

    لوحة_الأزرار = [
        [InlineKeyboardButton("🛍 الخدمات", callback_data='الخدمات')],
        [InlineKeyboardButton("📦 الطلبات", callback_data='الطلبات')],
        [InlineKeyboardButton("🎁 الهدية", callback_data='الهدية')],
        [InlineKeyboardButton("📊 قائمة المستخدمين والطلبات", callback_data='قائمة المستخدمين والطلبات')],
        [InlineKeyboardButton("🔍 تتبع الطلب", callback_data='تتبع الطلب')],
        [InlineKeyboardButton("💳 شحن النقاط", callback_data='شحن النقاط')],
    ]
    if user_id in admins:
        لوحة_الأزرار.append([InlineKeyboardButton("⚙️ الإعدادات", callback_data='الإعدادات')])

    رد_اللوحة = InlineKeyboardMarkup(لوحة_الأزرار)
    await update.message.reply_text(معلومات_النص + 'اختر الخدمة التي تريدها', reply_markup=رد_اللوحة)

async def زر(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    الاستفسار = update.callback_query
    await الاستفسار.answer()

    if الاستفسار.data == 'الخدمات':
        لوحة_الخدمات = [
            [InlineKeyboardButton("📸 خدمات إنستا", callback_data='خدمات_إنستا')],
            [InlineKeyboardButton("💬 خدمات تليجرام", callback_data='خدمات_تليجرام')],
            [InlineKeyboardButton("🎵 خدمات تيك توك", callback_data='خدمات_تيك_توك')],
            [InlineKeyboardButton("📘 خدمات فيسبوك", callback_data='خدمات_فيسبوك')],
            [InlineKeyboardButton("📺 خدمات يوتيوب", callback_data='خدمات_يوتيوب')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='رجوع_الرئيسية')]
        ]
        رد_الخدمات = InlineKeyboardMarkup(لوحة_الخدمات)
        await الاستفسار.edit_message_text('اختر الخدمة التي تريدها', reply_markup=رد_الخدمات)

    elif الاستفسار.data == 'رجوع_الرئيسية':
        await ابدأ(update.callback_query, context)

    elif الاستفسار.data.startswith('خدمات_'):
        category = CATEGORY_MAP[الاستفسار.data]
        context.user_data['current_category'] = category
        category_services = services.get(category.lower(), {})
        لوحة_الخدمات = [
            [InlineKeyboardButton(service['name'], callback_data=f"service_{category}_{id}")]
            for id, service in category_services.items()
        ]
        لوحة_الخدمات.append([InlineKeyboardButton("🔙 رجوع", callback_data='الخدمات')])
        رد_الخدمات = InlineKeyboardMarkup(لوحة_الخدمات)
        await الاستفسار.edit_message_text('اختر الخدمة التي تريدها', reply_markup=رد_الخدمات)

    elif الاستفسار.data.startswith('service_'):
        parts = الاستفسار.data.split('_')
        category = parts[1].lower()
        service_id = parts[2]
        context.user_data['service_id'] = service_id
        service = services[category].get(service_id)
        if service:
            النص = (f"📌 اسم الخدمة: {service['name']}\n"
                    f"💰 السعر لكل 1000: {service['price']}\n"
                    f"📉 الحد الأدنى للطلب: {service['min']}\n"
                    f"📈 الحد الأقصى للطلب: {service['max']}\n"
                    f"📝 الوصف: {service['description']}\n\n"
                    "أدخل العدد المطلوب:")
            await الاستفسار.edit_message_text(text=النص)
            context.user_data['state'] = STATES['QUANTITY']
            return STATES['QUANTITY']
        else:
            await الاستفسار.edit_message_text("حدث خطأ. الخدمة غير موجودة.")

    elif الاستفسار.data == 'إضافة خدمة' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text("أدخل اسم الخدمة:")
        context.user_data['state'] = STATES['NAME']
        return STATES['NAME']

    elif الاستفسار.data == 'شحن نقاط للمستخدم' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text("أدخل معرف المستخدم أو اسم المستخدم:")
        context.user_data['state'] = STATES['ADD_POINTS_USER']
        return STATES['ADD_POINTS_USER']

    elif الاستفسار.data == 'خصم النقاط' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text("أدخل معرف المستخدم أو اسم المستخدم:")
        context.user_data['state'] = STATES['DEDUCT_POINTS_USER']
        return STATES['DEDUCT_POINTS_USER']

    elif الاستفسار.data == 'شحن النقاط':
        await الاستفسار.edit_message_text(text=charge_description + "\n@channel_or_user")
    
    elif الاستفسار.data == 'تحديد وصف شحن النقاط' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text(text="أدخل الوصف الجديد لشحن النقاط:")
        context.user_data['state'] = STATES['SET_DESCRIPTION']
        return STATES['SET_DESCRIPTION']

    elif الاستفسار.data == 'تعيين أدمن' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text(text="أدخل معرف المستخدم أو اسم المستخدم الذي تريد تعيينه كأدمن:")
        context.user_data['state'] = STATES['SET_ADMIN_USER']
        return STATES['SET_ADMIN_USER']

    elif الاستفسار.data == 'إزالة أدمن' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text(text="أدخل معرف المستخدم أو اسم المستخدم الذي تريد إزالته من قائمة الأدمن:")
        context.user_data['state'] = STATES['REMOVE_ADMIN_USER']
        return STATES['REMOVE_ADMIN_USER']

    elif الاستفسار.data == 'تغيير API' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text("أدخل API_BASE_URL الجديد:")
        context.user_data['state'] = STATES['SET_API_DETAILS']
        return STATES['SET_API_DETAILS']

    elif الاستفسار.data == 'الإعدادات' and الاستفسار.from_user.id in admins:
        لوحة_الإعدادات = [
            [InlineKeyboardButton("➕ إضافة خدمة", callback_data='إضافة خدمة')],
            [InlineKeyboardButton("🔼 شحن نقاط للمستخدم", callback_data='شحن نقاط للمستخدم')],
            [InlineKeyboardButton("🔽 خصم النقاط", callback_data='خصم النقاط')],
            [InlineKeyboardButton("🎁 تحديد نقاط الهدية", callback_data='تحديد نقاط الهدية')],
            [InlineKeyboardButton("💬 تحديد وصف شحن النقاط", callback_data='تحديد وصف شحن النقاط')],
            [InlineKeyboardButton("👑 تعيين أدمن", callback_data='تعيين أدمن')],
            [InlineKeyboardButton("🚫 إزالة أدمن", callback_data='إزالة أدمن')],
            [InlineKeyboardButton("🔄 تغيير API", callback_data='تغيير API')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='رجوع_الرئيسية')]
        ]
        رد_الإعدادات = InlineKeyboardMarkup(لوحة_الإعدادات)
        await الاستفسار.edit_message_text('الإعدادات:', reply_markup=رد_الإعدادات)

    elif الاستفسار.data == 'الطلبات':
        user_id = الاستفسار.from_user.id
        orders = user_orders.get(str(user_id), [])
        if orders:
            order_texts = [f"طلب {order['order_id']}: {order['service']} - {order['quantity']}" for order in orders]
            نص = "\n".join(order_texts)
        else:
            نص = "لا توجد طلبات متاحة."
        نص += "\n\nاختر الطلب لرؤية التفاصيل:"
        لوحة_الطلبات = [
            [InlineKeyboardButton(order['order_id'], callback_data=f"order_{order['order_id']}")]
            for order in orders
        ]
        لوحة_الطلبات.append([InlineKeyboardButton("🔙 رجوع", callback_data='رجوع_الرئيسية')])
        رد_الطلبات = InlineKeyboardMarkup(لوحة_الطلبات)
        await الاستفسار.edit_message_text(نص, reply_markup=رد_الطلبات)

    elif الاستفسار.data.startswith('order_'):
        order_id = الاستفسار.data.split('_')[1]
        user_id = الاستفسار.from_user.id
        orders = [order for user, user_orders_list in user_orders.items() for order in user_orders_list if order['order_id'] == order_id]
        if orders:
            order = orders[0]
            # تحديث حالة الطلب من API
            response = requests.get(f"{API_BASE_URL}/status", params={"key": API_KEY, "order": order_id})
            if response.status_code == 200:
                order_status = response.json().get('status', 'unknown')
                order['status'] = order_status
            else:
                order_status = order.get('status', 'unknown')

            order_status = "مكتمل" if order_status == "completed" else "ملغي" if order_status == "canceled" else "جزئي" if order_status == "partial" else "في الانتظار"
            النص = (f"تفاصيل الطلب:\n\n"
                    f"📦 معرف الطلب: {order['order_id']}\n"
                    f"📌 الخدمة: {order['service']}\n"
                    f"🔢 الكمية: {order['quantity']}\n"
                    f"🔍 الحالة: {order_status}")
            await الاستفسار.edit_message_text(text=النص)
        else:
            await الاستفسار.edit_message_text("لم يتم العثور على تفاصيل الطلب.")

    elif الاستفسار.data == 'تحديد نقاط الهدية' and الاستفسار.from_user.id in admins:
        await الاستفسار.edit_message_text(text="أدخل عدد النقاط للهدية:")
        context.user_data['state'] = STATES['SET_GIFT_POINTS']
        return STATES['SET_GIFT_POINTS']

    elif الاستفسار.data.startswith('confirm_'):
        confirm_data = الاستفسار.data.split('_')[1]
        if confirm_data == 'yes':
            user_id = الاستفسار.from_user.id
            points = user_points.get(str(user_id), 0)
            total_price = context.user_data['total_price']
            if points >= total_price:
                data = {
                    'key': API_KEY,
                    'action': 'add',
                    'service': context.user_data['service_id'],
                    'link': context.user_data['link'],
                    'quantity': context.user_data['quantity']
                }
                response = requests.post(f"{API_BASE_URL}", data=data)
                if response.status_code == 200:
                    order = response.json()
                    user_points[str(user_id)] -= total_price
                    user_orders.setdefault(str(user_id), []).append({
                        'order_id': order['order'],
                        'service': services[context.user_data['current_category']][context.user_data['service_id']]['name'],
                        'quantity': context.user_data['quantity'],
                        'status': 'pending'  # الحالة الافتراضية للطلب الجديد
                    })
                    with shelve.open("bot_data") as db:
                        db["user_points"] = user_points
                        db["user_orders"] = user_orders
                    النص = f"تم إضافة الطلب بنجاح! معرف الطلب: {order['order']}\nالنقاط المتبقية: {user_points[str(user_id)]}"
                else:
                    النص = "حدث خطأ أثناء إضافة الطلب."
            else:
                النص = "ليس لديك نقاط كافية لإكمال الطلب."
            await الاستفسار.edit_message_text(text=النص)
        else:
            await الاستفسار.edit_message_text("تم إلغاء الطلب.")
        return ConversationHandler.END

    elif الاستفسار.data == 'قائمة المستخدمين والطلبات':
        total_users = len(user_points)
        total_orders = sum(len(orders) for orders in user_orders.values())
        نص = (f"📊 قائمة المستخدمين والطلبات:\n\n"
                f"🔢 إجمالي المستخدمين: {total_users}\n"
                f"📦 إجمالي الطلبات: {total_orders}")
        لوحة_رجوع = [[InlineKeyboardButton("🔙 رجوع", callback_data='رجوع_الرئيسية')]]
        رد_رجوع = InlineKeyboardMarkup(لوحة_رجوع)
        await الاستفسار.edit_message_text(text=نص, reply_markup=رد_رجوع)

    elif الاستفسار.data == 'تتبع الطلب':
        await الاستفسار.edit_message_text(text="أدخل رقم الطلب:")
        context.user_data['state'] = STATES['TRACK_ORDER']
        return STATES['TRACK_ORDER']

    elif الاستفسار.data == 'الهدية':
        user_id = الاستفسار.from_user.id
        now = datetime.now()
        last_gift_time = user_daily_gift.get(user_id)
        if last_gift_time and now - last_gift_time < timedelta(hours=24):
            remaining_time = timedelta(hours=24) - (now - last_gift_time)
            await الاستفسار.edit_message_text(f"لقد حصلت على الهدية اليومية بالفعل. الرجاء المحاولة بعد {remaining_time}.")
        else:
            user_points[str(user_id)] = user_points.get(str(user_id), 0) + daily_gift_points
            user_daily_gift[user_id] = now
            with shelve.open("bot_data") as db:
                db["user_points"] = user_points
                db["user_daily_gift"] = user_daily_gift
            await الاستفسار.edit_message_text(f"تم منحك {daily_gift_points} نقاط كهدية يومية. النقاط الحالية: {user_points[str(user_id)]}")

async def admin_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.message.from_user.id
    if user_id not in admins:
        await update.message.reply_text("أنت لست مشرف البوت!")
        return ConversationHandler.END

    state = context.user_data.get('state', STATES['NAME'])
    print(f"Current state: {state}")  # رسالة للتصحيح

    if state == STATES['NAME']:
        context.user_data['service_name'] = text
        context.user_data['state'] = STATES['ID']
        await update.message.reply_text("أدخل معرف الخدمة:")
        return STATES['ID']

    elif state == STATES['ID']:
        context.user_data['service_id'] = text
        context.user_data['state'] = STATES['PRICE']
        await update.message.reply_text("أدخل سعر الخدمة لكل 1000:")
        return STATES['PRICE']

    elif state == STATES['PRICE']:
        context.user_data['price'] = text
        context.user_data['state'] = STATES['MIN']
        await update.message.reply_text("أدخل الحد الأدنى للطلب:")
        return STATES['MIN']

    elif state == STATES['MIN']:
        context.user_data['min'] = text
        context.user_data['state'] = STATES['MAX']
        await update.message.reply_text("أدخل الحد الأقصى للطلب:")
        return STATES['MAX']

    elif state == STATES['MAX']:
        context.user_data['max'] = text
        context.user_data['state'] = STATES['DESCRIPTION']
        await update.message.reply_text("أدخل وصف الخدمة:")
        return STATES['DESCRIPTION']

    elif state == STATES['DESCRIPTION']:
        context.user_data['description'] = text
        await update.message.reply_text("اختر القسم الذي تريد إضافة الخدمة إليه:")
        لوحة_الأقسام = [
            [InlineKeyboardButton("📸 خدمات إنستا", callback_data='خدمات_إنستا')],
            [InlineKeyboardButton("💬 خدمات تليجرام", callback_data='خدمات_تليجرام')],
            [InlineKeyboardButton("🎵 خدمات تيك توك", callback_data='خدمات_تيك_توك')],
            [InlineKeyboardButton("📘 خدمات فيسبوك", callback_data='خدمات_فيسبوك')],
            [InlineKeyboardButton("📺 خدمات يوتيوب", callback_data='خدمات_يوتيوب')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='رجوع_الرئيسية')]
        ]
        رد_الأقسام = InlineKeyboardMarkup(لوحة_الأقسام)
        await update.message.reply_text('اختر القسم:', reply_markup=رد_الأقسام)
        context.user_data['state'] = STATES['ADD_SERVICE']
        return STATES['ADD_SERVICE']

async def add_service_to_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    category_key = query.data
    category = CATEGORY_MAP[category_key]
    service_id = context.user_data['service_id']
    services[category][service_id] = {
        'name': context.user_data['service_name'],
        'price': context.user_data['price'],
        'min': context.user_data['min'],
        'max': context.user_data['max'],
        'description': context.user_data['description']
    }
    with shelve.open("bot_data") as db:
        db["services"] = services
    print(f"Service added to {category}: {services[category][service_id]}")  # طباعة للتصحيح
    await query.edit_message_text("تم إضافة الخدمة بنجاح!")
    return ConversationHandler.END

async def add_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    state = context.user_data.get('state')

    if state == STATES['QUANTITY']:
        try:
            quantity = int(text)  # تحويل الكمية إلى عدد صحيح
            service_id = context.user_data['service_id']
            category = context.user_data['current_category']
            service = services[category.lower()][service_id]
            price_per_1000 = float(service['price'])
            total_price = (quantity / 1000) * price_per_1000
            context.user_data['quantity'] = quantity
            context.user_data['total_price'] = total_price
            النص = f"السعر الكلي للكمية المطلوبة ({quantity}): {total_price}\n\nأدخل رابط حسابك:"
            await update.message.reply_text(text=النص)
            context.user_data['state'] = STATES['LINK']
            return STATES['LINK']
        except ValueError:
            await update.message.reply_text("الرجاء إدخال عدد صحيح.")
            return STATES['QUANTITY']

    elif state == STATES['LINK']:
        context.user_data['link'] = text
        confirm_buttons = [
            [InlineKeyboardButton("✅ نعم", callback_data='confirm_yes')],
            [InlineKeyboardButton("❌ لا", callback_data='confirm_no')]
        ]
        رد_تأكيد = InlineKeyboardMarkup(confirm_buttons)
        await update.message.reply_text(f"تأكيد الطلب؟", reply_markup=رد_تأكيد)
        return STATES['CONFIRM']

async def track_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    order_id = text
    user_id = update.message.from_user.id
    orders = [order for user, user_orders_list in user_orders.items() for order in user_orders_list if order['order_id'] == order_id]
    if orders:
        order = orders[0]
        # تحديث حالة الطلب من API
        response = requests.get(f"{API_BASE_URL}/status", params={"key": API_KEY, "order": order_id})
        if response.status_code == 200:
            order_status = response.json().get('status', 'unknown')
            order['status'] = order_status
        else:
            order_status = order.get('status', 'unknown')

        order_status = "مكتمل" if order_status == "completed" else "ملغي" if order_status == "canceled" else "جزئي" if order_status == "partial" else "في الانتظار"
        النص = (f"تفاصيل الطلب:\n\n"
                f"📦 معرف الطلب: {order['order_id']}\n"
                f"📌 الخدمة: {order['service']}\n"
                f"🔢 الكمية: {order['quantity']}\n"
                f"🔍 الحالة: {order_status}")
        await update.message.reply_text(text=النص)
    else:
        await update.message.reply_text("لم يتم العثور على تفاصيل الطلب.")
    return ConversationHandler.END

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    state = context.user_data.get('state')

    if state == STATES['ADD_POINTS_USER']:
        user_id_or_username = text
        try:
            user_id = int(user_id_or_username)
        except ValueError:
            user_id = None
            for user in context.bot_data.get('users', {}).values():
                if user['username'] == user_id_or_username:
                    user_id = user['id']
                    break
        if user_id:
            context.user_data['user_id'] = user_id
            context.user_data['state'] = STATES['ADD_POINTS_AMOUNT']
            await update.message.reply_text("أدخل عدد النقاط المراد شحنها:")
            return STATES['ADD_POINTS_AMOUNT']
        else:
            await update.message.reply_text("لم يتم العثور على المستخدم. الرجاء إدخال معرف المستخدم أو اسم المستخدم:")
            return STATES['ADD_POINTS_USER']

    elif state == STATES['ADD_POINTS_AMOUNT']:
        user_id = context.user_data['user_id']
        points = int(text)
        user_points[str(user_id)] = user_points.get(str(user_id), 0) + points
        with shelve.open("bot_data") as db:
            db["user_points"] = user_points
        await update.message.reply_text(f"تم شحن {points} نقاط للمستخدم {user_id}.\nالنقاط الحالية: {user_points[str(user_id)]}")
        return ConversationHandler.END

async def deduct_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    state = context.user_data.get('state')

    if state == STATES['DEDUCT_POINTS_USER']:
        user_id_or_username = text
        try:
            user_id = int(user_id_or_username)
        except ValueError:
            user_id = None
            for user in context.bot_data.get('users', {}).values():
                if user['username'] == user_id_or_username:
                    user_id = user['id']
                    break
        if user_id:
            context.user_data['user_id'] = user_id
            context.user_data['state'] = STATES['DEDUCT_POINTS_AMOUNT']
            await update.message.reply_text("أدخل عدد النقاط المراد خصمها:")
            return STATES['DEDUCT_POINTS_AMOUNT']
        else:
            await update.message.reply_text("لم يتم العثور على المستخدم. الرجاء إدخال معرف المستخدم أو اسم المستخدم:")
            return STATES['DEDUCT_POINTS_USER']

    elif state == STATES['DEDUCT_POINTS_AMOUNT']:
        user_id = context.user_data['user_id']
        points = int(text)
        if user_points.get(str(user_id), 0) >= points:
            user_points[str(user_id)] -= points
            with shelve.open("bot_data") as db:
                db["user_points"] = user_points
            await update.message.reply_text(f"تم خصم {points} نقاط من المستخدم {user_id}.\nالنقاط الحالية: {user_points[str(user_id)]}")
        else:
            await update.message.reply_text("النقاط غير كافية للخصم.")
        return ConversationHandler.END

async def set_gift_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    try:
        points = int(text)
        global gift_points
        gift_points = points
        with shelve.open("bot_data") as db:
            db["gift_points"] = gift_points
        await update.message.reply_text(f"تم تعيين نقاط الهدية إلى {points} نقاط.")
    except ValueError:
        await update.message.reply_text("الرجاء إدخال عدد صحيح.")
    return ConversationHandler.END

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global charge_description
    charge_description = update.message.text
    with shelve.open("bot_data") as db:
        db["charge_description"] = charge_description
    await update.message.reply_text("تم تعيين الوصف الجديد لشحن النقاط.")
    return ConversationHandler.END

async def set_admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_or_username = update.message.text
    try:
        user_id = int(user_id_or_username)
    except ValueError:
        user_id = None
        for user in context.bot_data.get('users', {}).values():
            if user['username'] == user_id_or_username:
                user_id = user['id']
                break
    if user_id:
        if user_id not in admins:
            admins.append(user_id)
            with shelve.open("bot_data") as db:
                db["admins"] = admins
            await update.message.reply_text(f"تم تعيين {user_id} كأدمن.")
        else:
            await update.message.reply_text(f"{user_id} هو بالفعل أدمن.")
    else:
        await update.message.reply_text("لم يتم العثور على المستخدم.")
    return ConversationHandler.END

async def remove_admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_or_username = update.message.text
    try:
        user_id = int(user_id_or_username)
    except ValueError:
        user_id = None
        for user in context.bot_data.get('users', {}).values():
            if user['username'] == user_id_or_username:
                user_id = user['id']
                break
    if user_id:
        if user_id in admins:
            admins.remove(user_id)
            with shelve.open("bot_data") as db:
                db["admins"] = admins
            await update.message.reply_text(f"تم إزالة {user_id} من قائمة الأدمن.")
        else:
            await update.message.reply_text(f"{user_id} ليس أدمن.")
    return ConversationHandler.END

async def set_api_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("أدخل API_BASE_URL الجديد:")
    context.user_data['state'] = 'SET_API_DETAILS_STEP_1'

async def set_api_details_step_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global API_BASE_URL
    API_BASE_URL = update.message.text
    await update.message.reply_text("أدخل API_KEY الجديد:")
    context.user_data['state'] = 'SET_API_DETAILS_STEP_2'

async def set_api_details_step_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global API_KEY
    API_KEY = update.message.text
    with shelve.open("bot_data") as db:
        db["API_BASE_URL"] = API_BASE_URL
        db["API_KEY"] = API_KEY
    await update.message.reply_text("تم تعيين API_BASE_URL و API_KEY الجديدين.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('تم إلغاء العملية.')
    return ConversationHandler.END

def الرئيسي() -> None:
    التطبيق = Application.builder().token("7043661652:AAGAfLk6Veqob5MpkCJX92_duX1UCoybQzs").build()  # استبدل YOUR_TELEGRAM_BOT_TOKEN برمز البوت الخاص بك

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(زر, pattern='إضافة خدمة|الخدمات|service_|شحن النقاط|شحن نقاط للمستخدم|خصم النقاط|تحديد وصف شحن النقاط|تعيين أدمن|إزالة أدمن|تغيير API|الهدية|الطلبات|تحديد نقاط الهدية|قائمة المستخدمين والطلبات|تتبع الطلب|الإعدادات'),
        ],
        states={
            STATES['NAME']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['ID']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['PRICE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['MIN']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['MAX']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['DESCRIPTION']: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_service)],
            STATES['ADD_SERVICE']: [CallbackQueryHandler(add_service_to_category, pattern='خدمات_.*')],
            STATES['SELECT_SERVICE']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_order)],
            STATES['QUANTITY']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_order)],
            STATES['LINK']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_order)],
            STATES['CONFIRM']: [CallbackQueryHandler(زر, pattern='confirm_')],
            STATES['ADD_POINTS_USER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_points)],
            STATES['ADD_POINTS_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_points)],
            STATES['DEDUCT_POINTS_USER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, deduct_points)],
            STATES['DEDUCT_POINTS_AMOUNT']: [MessageHandler(filters.TEXT & ~filters.COMMAND, deduct_points)],
            STATES['SET_GIFT_POINTS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_gift_points)],
            STATES['SET_DESCRIPTION']: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_description)],
            STATES['SET_ADMIN_USER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_admin_user)],
            STATES['REMOVE_ADMIN_USER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_user)],
            STATES['SET_API_DETAILS']: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_details)],
            'SET_API_DETAILS_STEP_1': [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_details_step_1)],
            'SET_API_DETAILS_STEP_2': [MessageHandler(filters.TEXT & ~filters.COMMAND, set_api_details_step_2)],
            STATES['TRACK_ORDER']: [MessageHandler(filters.TEXT & ~filters.COMMAND, track_order)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    التطبيق.add_handler(CommandHandler("start", ابدأ))
    التطبيق.add_handler(conv_handler)
    التطبيق.add_handler(CallbackQueryHandler(زر))

    التطبيق.run_polling()

if __name__ == '__main__':
    الرئيسي()
  
