import logging
import asyncio
from datetime import datetime
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import config
import database as db

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# حالات المحادثات
(
    WAIT_BUY_QUANTITY,
    WAIT_DEP_RECEIPT,
    WAIT_DEP_TRX_REF,
    ADM_APPROVE_DEP_AMOUNT,
    ADM_ADD_CAT_NAME,
    ADM_ADD_SUBCAT_NAME,
    ADM_ADD_PROD_NAME,
    ADM_ADD_PROD_PRICE,
    ADM_ADD_PROD_WARRANTY,
    ADM_ADD_PROD_DELIVERY,
    ADM_ADD_PROD_DESC,
    ADM_ADD_KEYS_TEXT,
    ADM_SET_BAL_USER,
    ADM_SET_BAL_AMOUNT,
    ADM_SET_KURAIMI_ACC,
    ADM_SET_KURAIMI_NAME,
    ADM_SET_JAIB_NUM,
    ADM_SET_JAIB_NAME,
) = range(18)

# ============================================
# إعداد قائمة الأوامر (Menu)
# ============================================
async def setup_commands(application: Application):
    commands = [
        BotCommand("start", "بدء تشغيل البوت / Start"),
        BotCommand("browse", "تصفح جميع المنتجات / Browse"),
        BotCommand("balance", "رصيد المحفظة / Balance"),
        BotCommand("pay", "خدمات وطرق الدفع / Payment"),
        BotCommand("orders", "سجل طلباتي / My Orders"),
        BotCommand("contact", "الدعم الفني / Support"),
    ]
    await application.bot.set_my_commands(commands)

# ============================================
# القائمة الرئيسية المضمنة (الأزرار)
# ============================================
def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🛒 تصفح المنتجات", callback_data="btn_browse"),
            InlineKeyboardButton("💰 رصيد المحفظة", callback_data="btn_balance"),
        ],
        [
            InlineKeyboardButton("📦 طلباتي", callback_data="btn_orders"),
            InlineKeyboardButton("💳 طرق الدفع", callback_data="btn_pay"),
        ],
        [
            InlineKeyboardButton("📞 تواصل معنا", callback_data="btn_contact"),
        ]
    ]
    if user_id in getattr(config, "ADMIN_IDS", []):
        buttons.append([InlineKeyboardButton("⚙️ لوحة تحكم الإدارة", callback_data="btn_admin")])
        
    return InlineKeyboardMarkup(buttons)

# ============================================
# أمر البدء (/start)
# ============================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    
    name = user.full_name if user.full_name else (user.first_name or "صديقنا")
    username_text = f"@{user.username}" if user.username else "لا يوجد"
    
    text = (
        f"👋 أهلاً بك **{name}**!\n"
        f"👤 اسم الحساب: {name}\n"
        f"🌐 اليوزر: {username_text}\n"
        f"🆔 الآيدي (Telegram ID): `{user.id}`\n\n"
        f"استخدم القائمة أدناه للبدء والتصفح:"
    )
    
    reply_markup = get_main_keyboard(user.id)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ============================================
# 1. تصفح الأقسام الرئيسية (Categories)
# ============================================
async def browse_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    
    categories = db.get_categories()
    text = "📁 **اختر القسم المطلوب / Select a category:**"
    buttons = []
    
    for cat in categories:
        buttons.append([InlineKeyboardButton(cat["name"], callback_data=f"cat_{cat['id']}")])
        
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="btn_start")])
    keyboard = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============================================
# 2. تصفح الأقسام الفرعية (Subcategories)
# ============================================
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cat_id = int(query.data.replace("cat_", ""))
    category = db.get_category(cat_id)
    if not category:
        await query.edit_message_text("❌ القسم غير موجود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_browse")]]))
        return
        
    subcategories = db.get_subcategories(cat_id)
    if not subcategories:
        text = f"📁 **{category['name']}**\n\nلا توجد أقسام فرعية متاحة حالياً."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_browse")]])
    else:
        text = f"📁 **اختر القسم الفرعي لـ {category['name']}:**"
        buttons = []
        for sub in subcategories:
            buttons.append([InlineKeyboardButton(sub["name"], callback_data=f"subcat_{sub['id']}")])
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="btn_browse")])
        keyboard = InlineKeyboardMarkup(buttons)
        
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============================================
# 3. عرض المنتجات المتاحة في القسم الفرعي (Products)
# ============================================
async def subcategory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    subcat_id = int(query.data.replace("subcat_", ""))
    subcat = db.get_subcategory(subcat_id)
    if not subcat:
        await query.edit_message_text("❌ القسم الفرعي غير موجود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_browse")]]))
        return
        
    products = db.get_products_by_subcategory(subcat_id)
    if not products:
        text = f"🛍️ **{subcat['name']}**\n\nلا توجد منتجات متوفرة في هذا القسم حالياً."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{subcat['category_id']}")]])
    else:
        text = (
            f"🛍️ **المنتجات المتاحة في {subcat['name']}:**\n\n"
            "اضغط على المنتج لعرض التفاصيل والشراء:"
        )
        buttons = []
        for prod in products:
            buttons.append([
                InlineKeyboardButton(
                    f"{prod['name']} — ${prod['price']:.2f} ({prod['stock_count']})",
                    callback_data=f"prod_{prod['id']}"
                )
            ])
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{subcat['category_id']}")])
        keyboard = InlineKeyboardMarkup(buttons)
        
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============================================
# 4. تفاصيل المنتج وزر الشراء
# ============================================
async def product_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prod_id = int(query.data.replace("prod_", ""))
    prod = db.get_product(prod_id)
    if not prod:
        await query.edit_message_text("❌ المنتج غير موجود.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_browse")]]))
        return
        
    stock = prod["stock_count"]
    
    text = (
        f"📦 **{prod['name']}**\n"
        f"💰 **السعر:** `${prod['price']:.2f}`\n"
        f"🛡️ **الضمان:** {prod['warranty']}\n"
        f"🚚 **طريقة التسليم:** {prod['delivery']}\n\n"
    )
    if prod["description"]:
        text += f"{prod['description']}\n\n"
        
    text += f"📦 **المخزون المتوفر:** `{stock}`"
    
    if stock > 0:
        buy_btn = InlineKeyboardButton(f"🛒 شراء — ${prod['price']:.2f}", callback_data=f"buy_req_{prod['id']}")
    else:
        buy_btn = InlineKeyboardButton("❌ Out of Stock / نفد المخزون", callback_data="out_of_stock_alert")
        
    buttons = [
        [buy_btn],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"subcat_{prod['subcategory_id']}")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def out_of_stock_alert_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ هذا المنتج غير متوفر في المخزون حالياً!", show_alert=True)

# ============================================
# 5. تدفق الشراء وإدخال الكمية
# ============================================
async def buy_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prod_id = int(query.data.replace("buy_req_", ""))
    prod = db.get_product(prod_id)
    if not prod:
        await query.edit_message_text("❌ المنتج غير موجود.")
        return ConversationHandler.END
        
    context.user_data["buying_prod_id"] = prod_id
    context.user_data["buying_prod_name"] = prod["name"]
    context.user_data["buying_prod_price"] = prod["price"]
    
    text = (
        f"🔢 **أدخل الكمية التي ترغب بشرائها من:**\n"
        f"\"{prod['name']}\"\n\n"
        f"💡 أو أرسل /cancel للإلغاء (تنتهي الصلاحية خلال 45 ثانية)"
    )
    
    await query.message.reply_text(text)
    return WAIT_BUY_QUANTITY

async def buy_quantity_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prod_id = context.user_data.get("buying_prod_id")
    user = update.effective_user
    
    try:
        qty = int(text)
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح وموجب للكمية.")
        return WAIT_BUY_QUANTITY
        
    result = db.purchase_product(user.id, prod_id, qty)
    
    if not result["success"]:
        await update.message.reply_text(f"❌ **تعذر إتمام الشراء:** {result['error']}\n\nيمكنك شحن رصيدك عبر زر 'طرق الدفع'.")
        return ConversationHandler.END
        
    # تسليم المفاتيح بنجاح
    keys_formatted = "\n".join(result["keys"])
    msg = (
        f"🔑 **المفاتيح / الأكواد المستلمة:**\n"
        f"```{keys_formatted}```\n\n"
        f"🎉 **تم إكمال طلبك بنجاح!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 **رقم الطلب:** `{result['order_code']}`\n"
        f"�️ **المنتج:** {result['product_name']}\n"
        f"🔢 **الكمية:** `{result['quantity']}`\n"
        f"💰 **الإجمالي المخصوم:** `${result['total_price']:.2f}`\n"
        f"💵 **رصيدك المتبقي:** `${result['new_balance']:.2f}`\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 سجل طلباتي", callback_data="btn_orders")],
        [InlineKeyboardButton("🛒 تصفح المزيد", callback_data="btn_browse")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="btn_start")]
    ])
    
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END

# ============================================
# الرصيد، الطلبات، الدفع، التواصل
# ============================================
async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_or_create_user(user.id, user.username or "", user.first_name or "")
    
    text = (
        f"💰 **رصيد المحفظة:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **المستخدم:** {user.first_name}\n"
        f"🆔 **المعرف:** `{user.id}`\n"
        f"💵 **الرصيد المتاح:** `${db_user['balance']:.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"يمكنك شحن رصيدك عبر وسائل الدفع المعتمدة."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 شحن الرصيد / الدفع", callback_data="btn_pay")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="btn_start")]
    ])
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    orders = db.get_user_orders(user.id)
    
    if not orders:
        text = "📦 **سجل طلباتي:**\n\nليس لديك أي طلبات سابقة حتى الآن."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 تصفح المنتجات والشراء", callback_data="btn_browse")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="btn_start")]
        ])
    else:
        text = f"📦 **سجل طلباتك السابقة ({len(orders)}):**\n━━━━━━━━━━━━━━━━━━━\n"
        buttons = []
        for o in orders[:8]:
            text += f"🔹 `{o['order_code']}` | **{o['product_name'][:25]}...** | `${o['price']:.2f}`\n"
            buttons.append([InlineKeyboardButton(f"📄 عرض تفاصيل {o['order_code']}", callback_data=f"view_ord_{o['order_code']}")])
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="btn_start")])
        keyboard = InlineKeyboardMarkup(buttons)
        
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def order_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    order_code = query.data.replace("view_ord_", "")
    order = db.get_order_by_code(order_code)
    if not order:
        await query.edit_message_text("❌ لم يتم العثور على الطلب.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_orders")]]))
        return
        
    text = (
        f"📄 **تفاصيل الطلب:** `{order['order_code']}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ **المنتج:** {order['product_name']}\n"
        f"🔢 **الكمية:** `{order['quantity']}`\n"
        f"💵 **الإجمالي:** `${order['price']:.2f}`\n"
        f"📅 **التاريخ:** `{order['created_at']}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔑 **المفاتيح المستلمة:**\n```{order['item_content']}```"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 سجل الطلبات", callback_data="btn_orders")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="btn_start")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def pay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"💳 **شحن الرصيد / الإيداع في المحفظة:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"اختر وسيلة الدفع بالأسفل للتحويل عبر تطبيقك المفضل:"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 محفظة جيب (Jaib)", callback_data="dep_info_jaib"),
        ],
        [
            InlineKeyboardButton("🏦 بنك الكريمي (Kuraimi)", callback_data="dep_info_kuraimi"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="btn_balance")]
    ])
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def dep_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_jaib = "jaib" in query.data
    if is_jaib:
        j_num = db.get_setting("jaib_number", "771591191").strip()
        j_name = db.get_setting("jaib_name", "عيسى عبدالكافي علي العبسي").strip()
        text = (
            f"📱 **بيانات التحويل عبر محفظة جيب (Jaib):**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **اسم المستفيد:**\n"
            f"`{j_name}`\n\n"
            f"🔢 **رقم المحفظة (اضغط للنسخ فوراً):**\n"
            f"`{j_num}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 **خطوات الشحن:**\n"
            f"1. اضغط على الرقم بالأعلى لنسخه.\n"
            f"2. افتح تطبيق جيب وحول المبلغ للرقم المنسوخ.\n"
            f"3. اضغط على زر **(✅ لقد قمت بالتحويل - إرسال الإشعار)** بالأسفل لإرسال صورة السند ورقم العملية."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ لقد قمت بالتحويل - إرسال الإشعار", callback_data="dep_start_jaib")],
            [InlineKeyboardButton("🔙 رجوع لوسائل الدفع", callback_data="btn_pay")]
        ])
    else:
        k_acc = db.get_setting("kuraimi_account", "123456789").strip()
        k_name = db.get_setting("kuraimi_name", "عيسى عبدالكافي علي العبسي").strip()
        text = (
            f"🏦 **بيانات التحويل عبر بنك الكريمي (Kuraimi):**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **اسم المستفيد:**\n"
            f"`{k_name}`\n\n"
            f"🔢 **رقم الحساب (اضغط للنسخ فوراً):**\n"
            f"`{k_acc}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💡 **خطوات الشحن:**\n"
            f"1. اضغط على الرقم بالأعلى لنسخه فوراً.\n"
            f"2. افتح تطبيق كريمي جوال وحول المبلغ للحساب المنسوخ.\n"
            f"3. اضغط على زر **(✅ لقد قمت بالتحويل - إرسال الإشعار)** بالأسفل لإرسال صورة السند ورقم العملية."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ لقد قمت بالتحويل - إرسال الإشعار", callback_data="dep_start_kuraimi")],
            [InlineKeyboardButton("🔙 رجوع لوسائل الدفع", callback_data="btn_pay")]
        ])
        
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def deposit_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_jaib = "jaib" in query.data
    method = "محفظة جيب (Jaib)" if is_jaib else "بنك الكريمي (Kuraimi)"
    context.user_data["dep_method"] = method
    
    text = (
        f"📸 **إرسال إشعار تحويل {method}:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"الآن يرجى إرسال **صورة سند / إشعار التحويل (Screenshot)** من التطبيق:\n\n"
        f"💡 أو أرسل /cancel للإلغاء"
    )
    await query.message.reply_text(text, parse_mode="Markdown")
    return WAIT_DEP_RECEIPT

async def deposit_receipt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = None
    is_doc = False
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        photo_file_id = update.message.document.file_id
        is_doc = True
    else:
        await update.message.reply_text("❌ يرجى إرسال صورة السند/الإشعار كصورة:")
        return WAIT_DEP_RECEIPT
        
    context.user_data["dep_photo_id"] = photo_file_id
    context.user_data["dep_is_doc"] = is_doc
    
    msg = (
        f"🔢 **الآن يرجى كتابة وإرسال رقم العملية / الحوالة (Transaction ID / Reference):**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"*(تجد رقم العملية مسجلاً في إشعار التحويل)*\n\n"
        f"💡 أو أرسل /cancel للإلغاء"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return WAIT_DEP_TRX_REF

async def deposit_trx_ref_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    trx_ref = update.message.text.strip()
    photo_file_id = context.user_data.get("dep_photo_id", "")
    is_doc = context.user_data.get("dep_is_doc", False)
    method = context.user_data.get("dep_method", "حوالة")
    
    # فحص منع الاحتيال وتكرار السندات القديمة (يشمل الأرقام العربية والإنجليزية والمسافات)
    normalized_ref = db.normalize_trx_ref(trx_ref)
    if not normalized_ref:
        await update.message.reply_text(
            "⚠️ **يرجى إرسال رقم عملية صحيح.**\n\nأعد إرسال رقم العملية أو أرسل /cancel للإلغاء:",
            parse_mode="Markdown"
        )
        return WAIT_DEP_TRX_REF

    if db.is_transaction_ref_exists(normalized_ref):
        await update.message.reply_text(
            "⚠️ **تنبيه أمني:** رقم العملية هذا تم استخدامه مسبقاً في النظام!\n\n❌ تم إلغاء الطلب لمنع تكرار السندات القديمة.",
            reply_markup=get_main_keyboard(user.id),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
        
    req_id = db.create_deposit_request(user.id, method, photo_file_id, normalized_ref)
    
    user_msg = (
        f"⏳ **تم استلام طلب التحقق والإيداع بنجاح!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 **رقم الطلب:** `DEP-{req_id}`\n"
        f"💳 **الطريقة:** {method}\n"
        f"🔢 **رقم العملية:** `{normalized_ref}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"يتم الآن فحص وتأكيد السند وتاريخه من قبل الإدارة، وسيتم شحن رصيدك فور التأكيد."
    )
    await update.message.reply_text(user_msg, reply_markup=get_main_keyboard(user.id), parse_mode="Markdown")
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    admin_caption = (
        f"🔔 **طلب إيداع وتحقق جديد!**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔖 **رقم الطلب:** `DEP-{req_id}`\n"
        f"👤 **العميل:** {user.first_name} (@{user.username or 'بدون معرف'})\n"
        f"🆔 **معرف العميل (ID):** `{user.id}`\n"
        f"💳 **الطريقة:** {method}\n"
        f"🔢 **رقم العملية / المرجع:** `{normalized_ref}`\n"
        f"📅 **وقت الإرسال:** `{now_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ **يرجى مراجعة تاريخ ووقت السند قبل القبول:**"
    )
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 قبول وتحديد المبلغ ($)", callback_data=f"adm_dep_setamt_{req_id}"),
            InlineKeyboardButton("❌ رفض السند", callback_data=f"adm_dep_rej_{req_id}")
        ]
    ])
    
    for admin_id in getattr(config, "ADMIN_IDS", []):
        try:
            if photo_file_id:
                if is_doc:
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=photo_file_id,
                        caption=admin_caption,
                        reply_markup=admin_keyboard,
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=photo_file_id,
                        caption=admin_caption,
                        reply_markup=admin_keyboard,
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_caption,
                    reply_markup=admin_keyboard,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error sending deposit notice to admin {admin_id}: {e}")
            
    return ConversationHandler.END

async def adm_dep_setamt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    req_id = int(query.data.replace("adm_dep_setamt_", ""))
    dep = db.get_deposit_request(req_id)
    if not dep or dep["status"] != "pending":
        await query.edit_message_caption(caption=f"{query.message.caption or ''}\n\n⚠️ **تنبيه:** تم اتخاذ إجراء مسبق على هذا الطلب.")
        return ConversationHandler.END
        
    context.user_data["approving_req_id"] = req_id
    
    await query.message.reply_text(
        f"✍️ **طلب DEP-{req_id}:**\nأدخل المبلغ الفعلي الموضح في السند بالدولار ($) لشحنه للمستخدم:\n*(مثال: `5` أو `10` أو `25.5`)*\n\n💡 أو أرسل /cancel للإلغاء",
        parse_mode="Markdown"
    )
    return ADM_APPROVE_DEP_AMOUNT

async def adm_dep_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace("$", "")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً للمبلغ بالدولار:")
        return ADM_APPROVE_DEP_AMOUNT
        
    req_id = context.user_data.get("approving_req_id")
    admin_user = update.effective_user
    
    result = db.approve_deposit_with_amount(req_id, amount)
    if not result:
        await update.message.reply_text("❌ لم يتم العثور على الطلب أو تمت معالجته مسبقاً.")
        return ConversationHandler.END
        
    await update.message.reply_text(
        f"✅ **تم قبول الطلب وشحن `${amount:.2f}` بنجاح!**\n👤 تم شحن رصيد العميل وإرسال إشعار فوري له.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]),
        parse_mode="Markdown"
    )
    
    try:
        client_msg = (
            f"🎉 **تم تأكيد حوالتك وشحن محفظتك بنجاح!**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 **المبلغ المضاف:** `${result['amount']:.2f}`\n"
            f"🔢 **رقم العملية:** `{result['transaction_ref']}`\n"
            f"💵 **رصيدك الحالي بالمحفظة:** `${result['new_balance']:.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"يمكنك الآن الشراء وتصفح المنتجات مباشرة!"
        )
        await context.bot.send_message(
            chat_id=result["telegram_id"],
            text=client_msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 تصفح المنتجات والشراء", callback_data="btn_browse")]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error notifying client: {e}")
        
    return ConversationHandler.END

async def adm_dep_rej_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    req_id = int(query.data.replace("adm_dep_rej_", ""))
    dep = db.get_deposit_request(req_id)
    if not dep or dep["status"] != "pending":
        await query.edit_message_caption(caption=f"{query.message.caption or ''}\n\n⚠️ **تنبيه:** تم اتخاذ إجراء مسبق على هذا الطلب.")
        return
        
    db.update_deposit_status(req_id, "rejected")
    admin_user = update.effective_user
    await query.edit_message_caption(
        caption=f"{query.message.caption or ''}\n\n❌ **تم رفض هذا السند.**\nبواسطة المشرف: {admin_user.first_name}",
        parse_mode="Markdown"
    )
    
    try:
        client_msg = (
            f"⚠️ **نعتذر منك، تم رفض السند (DEP-{req_id}).**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"السبب المحتمل: تاريخ السند غير مطابق أو قديم، أو بيانات التحويل غير صحيحة.\n"
            f"يرجى التواصل مع الدعم الفني للمساعدة."
        )
        await context.bot.send_message(
            chat_id=dep["telegram_id"],
            text=client_msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 التواصل مع الدعم", callback_data="btn_contact")]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error notifying client: {e}")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support = db.get_setting("support_contact", "@tomamoh12").strip()
    clean_username = support.replace("@", "")
    
    text = (
        f"🌟 **مرحباً بك في مركز الدعم الفني وخدمة العملاء!** 🌟\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"يسعدنا دائماً تقديم المساعدة والإجابة على استفساراتكم بكل رحابة صدر.\n\n"
        f"💎 **خدماتنا المتاحة:**\n"
        f"• المساعدة في تفعيل وشراء المنتجات والمفاتيح.\n"
        f"• تأكيد ومتابعة عمليات شحن الرصيد والإيداع.\n"
        f"• حل أي مشكلة أو استفسار تقني على مدار الساعة.\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **مسؤول الدعم الفني:** `@{clean_username}`\n"
        f"🆔 **معرّف حسابك (ID):** `{update.effective_user.id}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *اضغط على الزر بالأسفل للتحدث مباشرة مع الدعم الفني:*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 مراسلة الدعم الفني مباشرة", url=f"https://t.me/{clean_username}")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="btn_start")]
    ])
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ============================================
# لوحة تحكم الإدارة بالكامل من الجوال (Admin Panel)
# ============================================
def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📁 إضافة قسم رئيسي", callback_data="adm_add_cat"),
            InlineKeyboardButton("📂 إضافة قسم فرعي", callback_data="adm_add_subcat"),
        ],
        [
            InlineKeyboardButton("➕ إضافة منتج", callback_data="adm_add_prod"),
            InlineKeyboardButton("🔑 شحن مفاتيح", callback_data="adm_add_keys"),
        ],
        [
            InlineKeyboardButton("🗑️ حذف قسم / فرعي / منتج", callback_data="adm_del_menu"),
        ],
        [
            InlineKeyboardButton("💵 تعديل رصيد مستخدم", callback_data="adm_set_bal"),
            InlineKeyboardButton("⚙️ إعدادات الدفع والصرف", callback_data="adm_pay_settings"),
        ],
        [
            InlineKeyboardButton("📊 إحصائيات المتجر", callback_data="adm_stats"),
        ],
        [InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="btn_start")]
    ])

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in getattr(config, "ADMIN_IDS", []):
        if update.callback_query:
            await update.callback_query.answer("⛔ Access Denied / ليس لديك صلاحية أدمن", show_alert=True)
        return

    text = (
        f"⚙️ **لوحة تحكم الإدارة الشاملة**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"مرحباً بك يا مدير (`{user.id}`)!\n"
        f"يمكنك إضافة الأقسام الرئيسية والفرعية والمنتجات وشحن المفاتيح وتعديل الأرصدة مباشرة:"
    )
    keyboard = get_admin_panel_keyboard()
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# إحصائيات
async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in getattr(config, "ADMIN_IDS", []):
        return
        
    users = db.get_all_users()
    orders = db.get_all_orders()
    products = db.get_all_products()
    total_sales = sum(o["price"] for o in orders)
    total_stock = sum(p["stock_count"] for p in products)
    
    text = (
        f"📊 **إحصائيات المتجر:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 المستخدمين: `{len(users)}`\n"
        f"📦 الطلبات المكتملة: `{len(orders)}`\n"
        f"💵 إجمالي المبيعات: `${total_sales:.2f}`\n"
        f"🛍️ عدد المنتجات: `{len(products)}`\n"
        f"🔑 المفاتيح المتاحة بالمخزون: `{total_stock}`\n"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

# 1. إضافة قسم رئيسي
async def adm_add_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📁 **أرسل اسم القسم الرئيسي الجديد (مثال: Antivirus):**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")]]))
    return ADM_ADD_CAT_NAME

async def adm_add_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    db.add_category(name)
    await update.message.reply_text(f"✅ تم إنشاء القسم الرئيسي: **{name}**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]), parse_mode="Markdown")
    return ConversationHandler.END

# 2. إضافة قسم فرعي
async def adm_add_subcat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = db.get_categories()
    if not categories:
        await query.edit_message_text("❌ لا توجد أقسام رئيسية. أضف قسماً رئيسياً أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_admin")]]))
        return
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(f"📁 {c['name']}", callback_data=f"adm_sel_mcat_{c['id']}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")])
    await query.edit_message_text("اختر القسم الرئيسي لإنشاء قسم فرعي تحته:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_sel_mcat_for_subcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_sel_mcat_", ""))
    context.user_data["adm_target_mcat_id"] = cat_id
    await query.edit_message_text("📂 **أرسل اسم القسم الفرعي الجديد (مثال: Kaspersky):**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")]]))
    return ADM_ADD_SUBCAT_NAME

async def adm_add_subcat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    cat_id = context.user_data["adm_target_mcat_id"]
    db.add_subcategory(cat_id, name)
    await update.message.reply_text(f"✅ تم إنشاء القسم الفرعي: **{name}** بنجاح!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]), parse_mode="Markdown")
    return ConversationHandler.END

# 3. إضافة منتج
async def adm_add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = db.get_categories()
    if not categories:
        await query.edit_message_text("❌ لا توجد أقسام.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_admin")]]))
        return
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(f"📁 {c['name']}", callback_data=f"adm_psel_mcat_{c['id']}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")])
    await query.edit_message_text("اختر القسم الرئيسي للمنتج:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_psel_mcat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_psel_mcat_", ""))
    subcategories = db.get_subcategories(cat_id)
    if not subcategories:
        await query.edit_message_text("⚠️ لا توجد أقسام فرعية في هذا القسم. أضف قسماً فرعياً أولاً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_admin")]]))
        return
    buttons = []
    for s in subcategories:
        buttons.append([InlineKeyboardButton(f"📂 {s['name']}", callback_data=f"adm_psel_sub_{s['id']}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")])
    await query.edit_message_text("اختر القسم الفرعي للمنتج:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_psel_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_psel_sub_", ""))
    context.user_data["adm_new_sub_id"] = sub_id
    await query.edit_message_text("🛍️ **أرسل اسم المنتج:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")]]))
    return ADM_ADD_PROD_NAME

async def adm_add_pname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["adm_new_pname"] = update.message.text.strip()
    await update.message.reply_text("💵 **أدخل سعر المنتج بالدولار ($):**\n(مثال: 50.00)")
    return ADM_ADD_PROD_PRICE

async def adm_add_pprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price < 0:
            raise ValueError()
        context.user_data["adm_new_pprice"] = price
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً.")
        return ADM_ADD_PROD_PRICE
        
    await update.message.reply_text("🛡️ **أدخل مدة الضمان (مثال: 365 Days أو أرسل '-' للافتراضي):**")
    return ADM_ADD_PROD_WARRANTY

async def adm_add_pwarranty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w = update.message.text.strip()
    context.user_data["adm_new_pwarranty"] = "365 Days" if w == "-" else w
    await update.message.reply_text("🚚 **طريقة التسليم (مثال: instant أو manual أو أرسل '-' للافتراضي):**")
    return ADM_ADD_PROD_DELIVERY

async def adm_add_pdelivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = update.message.text.strip()
    context.user_data["adm_new_pdelivery"] = "Instant" if d == "-" else d
    await update.message.reply_text("📝 **أدخل وصف وتعليمات المنتج (أو أرسل '-' للتخطي):**")
    return ADM_ADD_PROD_DESC

async def adm_add_pdesc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""
    sub_id = context.user_data["adm_new_sub_id"]
    name = context.user_data["adm_new_pname"]
    price = context.user_data["adm_new_pprice"]
    warranty = context.user_data["adm_new_pwarranty"]
    delivery = context.user_data["adm_new_pdelivery"]
    
    prod_id = db.add_product(sub_id, name, desc, price, warranty, delivery)
    
    await update.message.reply_text(
        f"✅ **تمت إضافة المنتج بنجاح!**\n🛍️ **{name}** | `${price:.2f}`\n\n👇 يمكنك شحن المفاتيح له الآن:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 شحن مفاتيح له الآن", callback_data=f"adm_fkey_{prod_id}")],
            [InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]
        ]),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# 4. شحن مفاتيح
async def adm_add_keys_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = db.get_all_products()
    if not products:
        await query.edit_message_text("❌ لا توجد منتجات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="btn_admin")]]))
        return
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(f"🔑 {p['name'][:30]} (المخزون: {p['stock_count']})", callback_data=f"adm_fkey_{p['id']}")])
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data="btn_admin")])
    await query.edit_message_text("اختر المنتج لشحن المفاتيح له:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_fkey_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.replace("adm_fkey_", ""))
    prod = db.get_product(prod_id)
    context.user_data["adm_key_prod_id"] = prod_id
    
    await query.edit_message_text(
        f"🔑 **شحن مفاتيح لمنتج: {prod['name']}**\n\n"
        f"أرسل الأكواد/المفاتيح في رسالة.\n"
        f"💡 *يمكنك وضع كل كود في سطر لإضافة كمية دفعة واحدة.*",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")]],
        parse_mode="Markdown"
    ))
    return ADM_ADD_KEYS_TEXT

async def adm_add_keys_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prod_id = context.user_data.get("adm_key_prod_id")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    count = db.add_product_items(prod_id, lines)
    total = db.get_available_stock_count(prod_id)
    
    await update.message.reply_text(
        f"✅ تمت إضافة `{count}` مفتاح/كود بنجاح!\n📦 إجمالي المخزون المتاح الآن: `{total}`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# 5. قائمة الحذف
async def adm_del_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف قسم رئيسي", callback_data="adm_d_cat_list")],
        [InlineKeyboardButton("🗑️ حذف قسم فرعي", callback_data="adm_d_sub_list")],
        [InlineKeyboardButton("🗑️ حذف منتج", callback_data="adm_d_prod_list")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="btn_admin")]
    ])
    await query.edit_message_text("اختر ما تريد حذفه:", reply_markup=keyboard)

async def adm_d_cat_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = db.get_categories()
    buttons = []
    for c in categories:
        buttons.append([InlineKeyboardButton(f"🗑️ {c['name']}", callback_data=f"adm_dodel_cat_{c['id']}")])
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data="adm_del_menu")])
    await query.edit_message_text("اختر القسم الرئيسي لحذفه:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_dodel_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("adm_dodel_cat_", ""))
    db.delete_category(cat_id)
    await query.edit_message_text("✅ تم حذف القسم وجميع ما بداخله بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]))

async def adm_d_sub_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categories = db.get_categories()
    buttons = []
    for c in categories:
        subs = db.get_subcategories(c["id"])
        for s in subs:
            buttons.append([InlineKeyboardButton(f"🗑️ {c['name']} > {s['name']}", callback_data=f"adm_dodel_sub_{s['id']}")])
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data="adm_del_menu")])
    await query.edit_message_text("اختر القسم الفرعي لحذفه:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_dodel_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.replace("adm_dodel_sub_", ""))
    db.delete_subcategory(sub_id)
    await query.edit_message_text("✅ تم حذف القسم الفرعي ومنتجاته.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]))

async def adm_d_prod_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = db.get_all_products()
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(f"🗑️ {p['name'][:30]}", callback_data=f"adm_dodel_prod_{p['id']}")])
    buttons.append([InlineKeyboardButton("🔙 إلغاء", callback_data="adm_del_menu")])
    await query.edit_message_text("اختر المنتج لحذفه نهائياً:", reply_markup=InlineKeyboardMarkup(buttons))

async def adm_dodel_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.replace("adm_dodel_prod_", ""))
    db.delete_product(prod_id)
    await query.edit_message_text("✅ تم حذف المنتج بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]))

# 6. تعديل رصيد
async def adm_set_bal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 **أرسل Telegram ID للمستخدم المراد تعديل رصيده:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="btn_admin")]]))
    return ADM_SET_BAL_USER

async def adm_set_bal_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        t_id = int(update.message.text.strip())
        target = db.get_user(t_id)
        if not target:
            await update.message.reply_text(f"❌ المستخدم `{t_id}` غير موجود في القاعدة. تأكد أنه أرسل /start أولاً.")
            return ADM_SET_BAL_USER
        context.user_data["target_tid"] = t_id
        await update.message.reply_text(f"👤 المستخدم: **{target['first_name']}**\n💰 الرصيد الحالي: `${target['balance']:.2f}`\n\n💵 **أدخل الرصيد الجديد بالدولار ($):**", parse_mode="Markdown")
        return ADM_SET_BAL_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً للـ ID.")
        return ADM_SET_BAL_USER

async def adm_set_bal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        t_id = context.user_data["target_tid"]
        db.set_user_balance(t_id, amount)
        await update.message.reply_text(f"✅ تم تعديل رصيد المستخدم `{t_id}` إلى `${amount:.2f}` بنجاح!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة الأدمن", callback_data="btn_admin")]]), parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً صحيحاً.")
        return ADM_SET_BAL_AMOUNT

# 7. إعدادات حسابات الدفع
async def adm_pay_settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    kuraimi_acc = db.get_setting("kuraimi_account", "123456789")
    kuraimi_name = db.get_setting("kuraimi_name", "عيسى عبدالكافي علي العبسي")
    jaib_num = db.get_setting("jaib_number", "771591191")
    jaib_name = db.get_setting("jaib_name", "عيسى عبدالكافي علي العبسي")
    
    text = (
        f"⚙️ **إعدادات حسابات الدفع:**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 **بنك الكريمي:**\n"
        f"• رقم الحساب: `{kuraimi_acc}`\n"
        f"• الاسم: `{kuraimi_name}`\n\n"
        f"📱 **محفظة جيب:**\n"
        f"• رقم المحفظة: `{jaib_num}`\n"
        f"• الاسم: `{jaib_name}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"اختر ما تريد تعديله:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 تعديل رقم حساب الكريمي", callback_data="adm_set_kuraimi")],
        [InlineKeyboardButton("� تعديل اسم صاحب الكريمي", callback_data="adm_set_kname")],
        [InlineKeyboardButton("� تعديل رقم محفظة جيب", callback_data="adm_set_jaib")],
        [InlineKeyboardButton("� تعديل اسم صاحب محفظة جيب", callback_data="adm_set_jname")],
        [InlineKeyboardButton("� لوحة الأدمن", callback_data="btn_admin")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def adm_set_kuraimi_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏦 **أرسل رقم حساب الكريمي الجديد:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_pay_settings")]]))
    return ADM_SET_KURAIMI_ACC

async def adm_set_kuraimi_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    db.set_setting("kuraimi_account", val)
    await update.message.reply_text(f"✅ تم تحديث رقم حساب الكريمي إلى: `{val}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إعدادات الدفع", callback_data="adm_pay_settings")]]), parse_mode="Markdown")
    return ConversationHandler.END

async def adm_set_kname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 **أرسل الاسم الجديد لصاحب حساب الكريمي:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_pay_settings")]]))
    return ADM_SET_KURAIMI_NAME

async def adm_set_kname_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    db.set_setting("kuraimi_name", val)
    await update.message.reply_text(f"✅ تم تحديث اسم صاحب الكريمي إلى: **{val}**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إعدادات الدفع", callback_data="adm_pay_settings")]]), parse_mode="Markdown")
    return ConversationHandler.END

async def adm_set_jaib_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📱 **أرسل رقم محفظة جيب الجديد:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_pay_settings")]]))
    return ADM_SET_JAIB_NUM

async def adm_set_jaib_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    db.set_setting("jaib_number", val)
    await update.message.reply_text(f"✅ تم تحديث رقم محفظة جيب إلى: `{val}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إعدادات الدفع", callback_data="adm_pay_settings")]]), parse_mode="Markdown")
    return ConversationHandler.END

async def adm_set_jname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 **أرسل الاسم الجديد لصاحب محفظة جيب:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_pay_settings")]]))
    return ADM_SET_JAIB_NAME

async def adm_set_jname_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    db.set_setting("jaib_name", val)
    await update.message.reply_text(f"✅ تم تحديث اسم صاحب محفظة جيب إلى: **{val}**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إعدادات الدفع", callback_data="adm_pay_settings")]]), parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await start_command(update, context)
    else:
        await update.message.reply_text("❌ تم الإلغاء / Aborted.", reply_markup=get_main_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ============================================
# تشغيل البوت
# ============================================
def main():
    token = getattr(config, "BOT_TOKEN", "").strip()
    proxy = getattr(config, "PROXY_URL", None)

    req_kwargs = {
        "connection_pool_size": 8,
        "connect_timeout": 30.0,
        "read_timeout": 30.0,
        "write_timeout": 30.0,
    }
    if proxy:
        req_kwargs["proxy"] = proxy

    t_request = HTTPXRequest(**req_kwargs)

    application = (
        Application.builder()
        .token(token)
        .request(t_request)
        .post_init(setup_commands)
        .build()
    )

    # محادثة الشراء والكمية
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_request_handler, pattern="^buy_req_")],
        states={
            WAIT_BUY_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_quantity_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), CallbackQueryHandler(cancel_conversation, pattern="^btn_start$")],
        per_chat=True,
    )

    # محادثة الإيداع والشحن (العميل)
    dep_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(deposit_start_handler, pattern="^dep_start_")
        ],
        states={
            WAIT_DEP_RECEIPT: [MessageHandler((filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, deposit_receipt_received)],
            WAIT_DEP_TRX_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_trx_ref_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), CallbackQueryHandler(cancel_conversation, pattern="^btn_start$")],
        per_chat=True,
    )

    # محادثة قبول وشحن الإيداع وتحديد المبلغ (الأدمن)
    adm_dep_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_dep_setamt_start, pattern="^adm_dep_setamt_")],
        states={
            ADM_APPROVE_DEP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_dep_amount_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    # محادثات لوحة الإدارة
    cat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_cat_start, pattern="^adm_add_cat$")],
        states={ADM_ADD_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_cat_name)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^btn_admin$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    subcat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_subcat_start, pattern="^adm_add_subcat$"), CallbackQueryHandler(adm_sel_mcat_for_subcat, pattern="^adm_sel_mcat_")],
        states={
            ADM_ADD_SUBCAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_subcat_name)],
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^btn_admin$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    prod_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_prod_start, pattern="^adm_add_prod$"), CallbackQueryHandler(adm_psel_sub, pattern="^adm_psel_sub_")],
        states={
            ADM_ADD_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_pname)],
            ADM_ADD_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_pprice)],
            ADM_ADD_PROD_WARRANTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_pwarranty)],
            ADM_ADD_PROD_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_pdelivery)],
            ADM_ADD_PROD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_pdesc)],
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^btn_admin$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    keys_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_add_keys_start, pattern="^adm_add_keys$"), CallbackQueryHandler(adm_fkey_selected, pattern="^adm_fkey_")],
        states={ADM_ADD_KEYS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_keys_received)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^btn_admin$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    bal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_bal_start, pattern="^adm_set_bal$")],
        states={
            ADM_SET_BAL_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_bal_user)],
            ADM_SET_BAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_bal_amount)],
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^btn_admin$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    kuraimi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_kuraimi_start, pattern="^adm_set_kuraimi$")],
        states={ADM_SET_KURAIMI_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_kuraimi_received)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^adm_pay_settings$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    kname_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_kname_start, pattern="^adm_set_kname$")],
        states={ADM_SET_KURAIMI_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_kname_received)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^adm_pay_settings$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    jaib_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_jaib_start, pattern="^adm_set_jaib$")],
        states={ADM_SET_JAIB_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_jaib_received)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^adm_pay_settings$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    jname_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_set_jname_start, pattern="^adm_set_jname$")],
        states={ADM_SET_JAIB_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_set_jname_received)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^adm_pay_settings$"), CommandHandler("cancel", cancel_conversation)],
        per_chat=True,
    )

    application.add_handler(buy_conv)
    application.add_handler(dep_conv)
    application.add_handler(adm_dep_conv)
    application.add_handler(cat_conv)
    application.add_handler(subcat_conv)
    application.add_handler(prod_conv)
    application.add_handler(keys_conv)
    application.add_handler(bal_conv)
    application.add_handler(kuraimi_conv)
    application.add_handler(kname_conv)
    application.add_handler(jaib_conv)
    application.add_handler(jname_conv)

    # أوامر النصوص
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("browse", browse_handler))
    application.add_handler(CommandHandler("balance", balance_handler))
    application.add_handler(CommandHandler("orders", orders_handler))
    application.add_handler(CommandHandler("pay", pay_handler))
    application.add_handler(CommandHandler("contact", contact_handler))
    application.add_handler(CommandHandler("admin", admin_panel_handler))

    # أحداث الإدارة ومراجعة الإيداع
    application.add_handler(CallbackQueryHandler(adm_dep_rej_handler, pattern="^adm_dep_rej_"))
    application.add_handler(CallbackQueryHandler(adm_pay_settings_handler, pattern="^adm_pay_settings$"))
    application.add_handler(CallbackQueryHandler(out_of_stock_alert_handler, pattern="^out_of_stock_alert$"))
    application.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^btn_admin$"))
    application.add_handler(CallbackQueryHandler(admin_stats_handler, pattern="^adm_stats$"))
    application.add_handler(CallbackQueryHandler(adm_psel_mcat, pattern="^adm_psel_mcat_"))
    application.add_handler(CallbackQueryHandler(adm_del_menu_handler, pattern="^adm_del_menu$"))
    application.add_handler(CallbackQueryHandler(adm_d_cat_list, pattern="^adm_d_cat_list$"))
    application.add_handler(CallbackQueryHandler(adm_dodel_cat, pattern="^adm_dodel_cat_"))
    application.add_handler(CallbackQueryHandler(adm_d_sub_list, pattern="^adm_d_sub_list$"))
    application.add_handler(CallbackQueryHandler(adm_dodel_sub, pattern="^adm_dodel_sub_"))
    application.add_handler(CallbackQueryHandler(adm_d_prod_list, pattern="^adm_d_prod_list$"))
    application.add_handler(CallbackQueryHandler(adm_dodel_prod, pattern="^adm_dodel_prod_"))

    # أحداث واجهة المستخدم
    application.add_handler(CallbackQueryHandler(start_command, pattern="^btn_start$"))
    application.add_handler(CallbackQueryHandler(browse_handler, pattern="^btn_browse$"))
    application.add_handler(CallbackQueryHandler(balance_handler, pattern="^btn_balance$"))
    application.add_handler(CallbackQueryHandler(orders_handler, pattern="^btn_orders$"))
    application.add_handler(CallbackQueryHandler(pay_handler, pattern="^btn_pay$"))
    application.add_handler(CallbackQueryHandler(dep_info_handler, pattern="^dep_info_"))
    application.add_handler(CallbackQueryHandler(contact_handler, pattern="^btn_contact$"))
    application.add_handler(CallbackQueryHandler(category_handler, pattern="^cat_"))
    application.add_handler(CallbackQueryHandler(subcategory_handler, pattern="^subcat_"))
    application.add_handler(CallbackQueryHandler(product_details_handler, pattern="^prod_"))
    application.add_handler(CallbackQueryHandler(order_details_handler, pattern="^view_ord_"))

    print("🤖 البوت يعمل الآن بنجاح مع قاعدة بيانات SQLite...")
    application.run_polling()

if __name__ == "__main__":
    main()
