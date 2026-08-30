import sqlite3
import os
import uuid
import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_database.sqlite")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # جدول المستخدمين
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول الأقسام الرئيسية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول الأقسام الفرعية
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subcategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
            )
        """)
        
        # جدول المنتجات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subcategory_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                price REAL NOT NULL,
                warranty TEXT DEFAULT '365 Days',
                delivery TEXT DEFAULT 'Instant',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subcategory_id) REFERENCES subcategories (id) ON DELETE CASCADE
            )
        """)
        
        # جدول المفاتيح والأكواد
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                item_content TEXT NOT NULL,
                is_sold INTEGER DEFAULT 0,
                sold_to_user_id INTEGER,
                sold_at TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)
        
        # جدول الطلبات والمشتريات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE,
                user_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                price REAL NOT NULL,
                item_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # جدول طلبات الشحن
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deposit_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                amount REAL DEFAULT 0.0,
                payment_method TEXT,
                receipt_photo_id TEXT,
                transaction_ref TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # التأكد من وجود عمود transaction_ref في حال كانت القاعدة قديمة
        cursor.execute("PRAGMA table_info(deposit_requests)")
        dep_cols = [c[1] for c in cursor.fetchall()]
        if "transaction_ref" not in dep_cols:
            cursor.execute("ALTER TABLE deposit_requests ADD COLUMN transaction_ref TEXT")
        
        # جدول الإعدادات ورسائل الدعم
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("""
            INSERT OR IGNORE INTO bot_settings (key, value) VALUES 
            ('support_contact', '@tomamoh12'),
            ('jaib_name', 'عيسى عبدالكافي علي العبسي'),
            ('jaib_number', '771591191'),
            ('kuraimi_name', 'عيسى عبدالكافي علي العبسي'),
            ('kuraimi_account', '123456789'),
            ('exchange_rate', '535'),
            ('payment_instructions', 'يرجى تحويل المبلغ ثم إرسال صورة الإشعار هنا.')
        """)
        
        # إضافة البيانات المبدئية عند أول إنشاء
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO categories (name) VALUES ('Microsoft Office')")
            office_cat_id = cursor.lastrowid
            
            cursor.execute("INSERT INTO categories (name) VALUES ('Microsoft Windows')")
            win_cat_id = cursor.lastrowid
            
            cursor.execute("INSERT INTO categories (name) VALUES ('Windows Servers')")
            srv_cat_id = cursor.lastrowid
            
            cursor.execute("INSERT INTO categories (name) VALUES ('VPN')")
            vpn_cat_id = cursor.lastrowid
            
            # أقسام فرعية لمايكروسوفت أوفيس
            subcats = [
                'Microsoft 365', 'Office 2010', 'Office 2016', 
                'Office 2019', 'Office 2021', 'Office 2024', 'Office 365'
            ]
            subcat_ids = {}
            for s in subcats:
                cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (office_cat_id, s))
                subcat_ids[s] = cursor.lastrowid
                    
            for s in ['Windows 10/11']:
                cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (win_cat_id, s))
                subcat_ids[s] = cursor.lastrowid
                
            for s in ['Microsoft Windows Server 2019', 'Microsoft Windows Server 2022', 'Microsoft Windows Server 2025', 'Microsoft Windows Server 2016']:
                cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (srv_cat_id, s))
                subcat_ids[s] = cursor.lastrowid
                
            for s in ['ExpressVPN', 'NordVPN', 'Surfshark']:
                cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (vpn_cat_id, s))
                subcat_ids[s] = cursor.lastrowid
                
            # منتجات Microsoft 365
            desc_365 = """✍️ ▫️ نوفر لك مفتاح أصلي لتفعيل الحساب مباشرة عبر موقع setup.office.com
▫️ يتطلب تشغيل VPN وقت التفعيل فقط حسب دولة المفتاح.
▫️ بعد التفعيل يعمل الحساب عالمياً وبدون الحاجة إلى VPN.
▫️ صالح لمدة 12 شهراً مع ضمان كامل طوال فترة الاشتراك."""
            
            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft 365'], 'Microsoft 365 Family "Key" 6Users - 12months - TW/HK/Macau SAR', desc_365, 50.00, '365 يوم', 'تسليم يدوي / manual'))
            p_365_1 = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft 365'], 'Microsoft 365 Personal "Key" 1User - 12months - TW/HK/Macau SAR', desc_365, 35.00, '365 يوم', 'تسليم يدوي / manual'))
            p_365_2 = cursor.lastrowid

            for i in range(8):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_365_1, f"GT6JC-NXWWC-KRQ96-2639M-CWHY{i+1}"))
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_365_2, f"PERSO-NXWWC-KRQ96-2639M-ABCD{i+1}"))

            # منتجات Office 2016 (مطابقة للصور)
            desc_2016_phone = """✍️ 👉 يمكن تفعيل جهاز واحد (1PC) عبر طريقة التفعيل بالهاتف.
👉 تفعيل لمرة واحدة فقط – لا نضمن إعادة التفعيل بعد عمل فورمات للجهاز.
👉 هذا المفتاح صالح لنظام ويندوز PC فقط (لا يدعم نظام Mac).

رابط التحميل: https://massgrave.dev/office_c2r_links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 2016'], 'Office 2016 Pro Plus Retail (Phone)', desc_2016_phone, 0.60, '7 أيام', 'يدوي'))
            p_2016_1 = cursor.lastrowid

            desc_2016_mac = """✍️ 👉 تفعيل جهاز ماك واحد (1 User for MAC).
👉 مفتاح أصلي Home & Business يربط بحساب مايكروسوفت.
👉 يدعم إعادة التثبيت بعد الفورمات لنفس الجهاز."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 2016'], 'Office 2016 HB 1 User for MAC', desc_2016_mac, 17.00, '30 يوم', 'يدوي'))
            p_2016_2 = cursor.lastrowid

            # مفاتيح Office 2016 (8 للأول و 2 للثاني مثل الصورة)
            for i in range(8):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_2016_1, f"OF16P-PHONE-KEY96-2639M-PHONE{i+1}"))
            for i in range(2):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_2016_2, f"OF16M-MAC01-HBKEY-2639M-MAC0{i+1}"))

            # منتجات Office 2019 (مطابقة للصور - 24 مفتاح)
            desc_2019_phone = """✍️ 👉 يمكن تفعيل جهاز واحد (1PC) عبر طريقة التفعيل بالهاتف.
👉 تفعيل لمرة واحدة فقط – لا نضمن إعادة التفعيل بعد عمل فورمات للجهاز.
👉 هذا المفتاح صالح لنظام ويندوز PC فقط (لا يدعم نظام Mac).

رابط التحميل: https://massgrave.dev/office_c2r_links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 2019'], 'Office 2019 Pro Plus Retail (Phone)', desc_2019_phone, 0.60, '7 أيام', 'يدوي'))
            p_2019 = cursor.lastrowid
            
            for i in range(24):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_2019, f"OF19P-PHONE-KEY96-2639M-PH{i+1:02d}"))

            # منتجات Office 2021 (مطابقة للصور - 7 مفاتيح)
            desc_2021_phone = """✍️ 👉 يمكن تفعيل جهاز واحد (1PC) عبر طريقة التفعيل بالهاتف.
👉 تفعيل لمرة واحدة فقط – لا نضمن إعادة التفعيل بعد عمل فورمات للجهاز.
👉 هذا المفتاح صالح لنظام ويندوز PC فقط (لا يدعم نظام Mac).

رابط التحميل: https://massgrave.dev/office_c2r_links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 2021'], 'Office 2021 Pro Plus Retail (Phone)', desc_2021_phone, 0.60, '7 أيام', 'تلقائي / auto'))
            p_2021 = cursor.lastrowid
            
            for i in range(7):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_2021, f"OF21P-PHONE-KEY96-2639M-PH{i+1:02d}"))

            # منتجات Office 2024 (مطابقة للصور - 30 مفتاح مع أسعار الكميات)
            desc_2024_ltsc = """📊 **أسعار الجملة والكميات:**
• 21–40 قطعة ← $0.50 / للقطعة
• 41–75 قطعة ← $0.45 / للقطعة
• +76 قطعة ← $0.40 / للقطعة

✍️ 👉 يمكن تفعيل جهاز واحد (1PC) عبر طريقة التفعيل بالهاتف.
👉 تفعيل لمرة واحدة فقط – لا نضمن إعادة التفعيل بعد عمل فورمات للجهاز.
👉 هذا المفتاح صالح لنظام ويندوز PC فقط (لا يدعم نظام Mac)."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 2024'], 'Office 2024 Pro Plus Ltsc (Phone)', desc_2024_ltsc, 0.60, '7 أيام', 'تلقائي / auto'))
            p_2024 = cursor.lastrowid
            
            for i in range(30):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_2024, f"OF24L-LTSC-KEY96-2639M-LTSC{i+1:02d}"))

            # منتجات Office 365 (مطابقة للصور - منتج نافد ومنتج به 100 حساب)
            desc_365_a3 = """✍️ 👉 مساحة تخزين 100GB OneDrive Storage
👉 حساب مدى الحياة (Lifetime Account)
👉 نوفر لك بيانات الدخول (الإيميل وكلمة السر)
👉 تسجيل دخول مباشر عبر office.com"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 365'], 'Office 365 A3 Account', desc_365_a3, 0.80, '90 يوم', 'تلقائي / auto'))
            # مخزون 0 مثل الصورة

            desc_365_e3 = """📊 **أسعار الجملة والكميات:**
• 20–40 قطعة ← $0.15 / للقطعة
• 41–100 قطعة ← $0.13 / للقطعة
• +101 قطعة ← $0.10 / للقطعة

✍️ 👉 مساحة تخزين 100GB OneDrive Storage
👉 استخدام سنة وأكثر (1 Year+ usage)
👉 نوفر لك بيانات الدخول (الإيميل وكلمة السر)
👉 تسجيل دخول مباشر عبر https://portal.office.com"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Office 365'], 'Office 365 E3 100GB Accounts', desc_365_e3, 0.20, '180 يوم', 'تلقائي / auto'))
            p_365_e3 = cursor.lastrowid

            for i in range(100):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_365_e3, f"user{i+1:03d}@office365-corp.com:Pass@{i+1:03d}!2026"))

            # ==================== منتجات Windows 10/11 (مطابقة للصور الـ 5) ====================
            
            # 1. Windows 10/11 Pro OEM Online (10 مفاتيح)
            desc_win_pro_oem = """✍️ 👉 نسبة التفعيل أونلاين أكثر من 90% (Online Activation Rate 90%+).
👉 مفاتيح OEM أصلية 100% صادرة من مايكروسوفت لمصنعي الأجهزة مثل Dell, HP, Asus, Toshiba.
👉 لا يمكن استخدام مفاتيح OEM للترقية من إصدار Home إلى Pro.
👉 ترتبط المفاتيح باللوحة الأم (Motherboard) ويتم إعادة التفعيل تلقائياً بعد إعادة تثبيت الويندوز.
👉 تفعيل مدى الحياة (Lifetime activation).
👉 تفعيل أونلاين يربط بالمذربورد."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10/11 Pro OEM Online', desc_win_pro_oem, 2.80, '7 أيام', 'يدوي / manual'))
            p_w1 = cursor.lastrowid
            for i in range(10):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w1, f"W1011-PROEM-KEY96-2639M-OEM{i+1:02d}"))

            # 2. Windows 10/11 Home OEM Online (8 مفاتيح)
            desc_win_home_oem = """✍️ 👉 مفاتيح OEM أصلية 100% صادرة من مايكروسوفت لمصنعي الأجهزة مثل Dell, HP, Asus, Toshiba.
👉 لا يمكن استخدام مفاتيح OEM للترقية (Can't be used to upgrade).
👉 ترتبط المفاتيح باللوحة الأم (Motherboard) ويتم إعادة التفعيل تلقائياً بعد إعادة التثبيت.
👉 تفعيل مدى الحياة (Lifetime activation).
👉 تفعيل أونلاين يربط بالمذربورد."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10/11 Home OEM Online', desc_win_home_oem, 0.80, '90 يوم', 'تلقائي / auto'))
            p_w2 = cursor.lastrowid
            for i in range(8):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w2, f"W1011-HOMEM-KEY96-2639M-OEM{i+1:02d}"))

            # 3. Windows 10/11 Pro Retail Online (11 مفتاح مع خصم كميات)
            desc_win_pro_retail = """📊 **أسعار الكميات:**
• +50 قطعة ← $0.80 / للقطعة

✍️ 👉 لا ترتبط هذه المفاتيح باللوحة الأم، وتدعم إعادة التثبيت إذا لم تتغير قطع الجهاز.
👉 تفعيل مدى الحياة (Lifetime activation).
👉 تفعيل أونلاين ويمكن نقل الترخيص لجهاز كمبيوتر آخر (Can transfer to other PCs)."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10/11 Pro Retail Online', desc_win_pro_retail, 0.90, '7 أيام', 'تلقائي / auto'))
            p_w3 = cursor.lastrowid
            for i in range(11):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w3, f"W1011-PRORT-KEY96-2639M-RET{i+1:02d}"))

            # 4. Windows 10 / 11 Pro 20PC - 30D [MAK:Volume] (5 مفاتيح)
            desc_win_mak_30d = """📝 👉 مفتاح ترخيص فوليوم (Volume) لنظام Windows 10 / 11 Pro يمكنه تفعيل حتى 20 جهاز كمبيوتر (20PC).
👉 تفعيل دائم مدى الحياة.
👉 تراخيص أصلية ومضمونة 100%.
👉 يرجى التأكد من اختيار الإصدار والكمية المناسبة لاحتياجاتك قبل الشراء، لا نقبل الاسترجاع أو الاستبدال بعد تسليم الطلب. إذا كان لديك أي استفسار، لا تتردد في التواصل معنا."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10 / 11 Pro 20PC - 30D [MAK:Volume]', desc_win_mak_30d, 55.00, '30 يوم', 'يدوي / manual'))
            p_w4 = cursor.lastrowid
            for i in range(5):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w4, f"W1011-MAK20-30DAY-2639M-MAK{i+1:02d}"))

            # 5. Windows 10 / 11 Pro 20PC [MAK:Volume] (2 مفاتيح)
            desc_win_mak_7d = """📝 👉 مفتاح ترخيص فوليوم (Volume) لنظام Windows 10 / 11 Pro يمكنه تفعيل حتى 20 جهاز كمبيوتر (20PC).
👉 تفعيل دائم مدى الحياة.
👉 تراخيص أصلية ومضمونة 100%.
👉 يرجى التأكد من اختيار الإصدار والكمية المناسبة لاحتياجاتك قبل الشراء، لا نقبل الاسترجاع أو الاستبدال بعد تسليم الطلب. إذا كان لديك أي استفسار، لا تتردد في التواصل معنا."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10 / 11 Pro 20PC [MAK:Volume]', desc_win_mak_7d, 45.00, '7 أيام', 'يدوي / manual'))
            p_w5 = cursor.lastrowid
            for i in range(2):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w5, f"W1011-MAK20-7DAYS-2639M-MAK{i+1:02d}"))

            # 6. Windows 10 / 11 Enterprise 1PC [MAK:Volume] (4 مفاتيح)
            desc_win_ent = """📝 👉 ستحصل على مفتاح ترخيص واحد Windows 10 / 11 Enterprise MAK يفعل جهاز كمبيوتر واحد (1PC).
👉 يمكن استخدام المفتاح على نفس الجهاز لإعادة التفعيل بعد إعادة التثبيت (فورمات).

روابط التحميل:
Windows 10 business - https://massgrave.dev/windows_10_links#download-links

Windows 11 business - https://massgrave.dev/windows_11_links#download-links

ملاحظة: (اختر نسخة "Business" Edition ISO من صفحة التحميل، لأنها تحتوي على "Enterprise" وليست النسخة الاستهلاكية العادية)"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Windows 10/11'], 'Windows 10 / 11 Enterprise 1PC [MAK:Volume]', desc_win_ent, 2.50, '7 أيام', 'يدوي / manual'))
            p_w6 = cursor.lastrowid
            for i in range(4):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_w6, f"W1011-ENTER-KEY96-2639M-ENT{i+1:02d}"))

            # ==================== منتجات Windows Server 2019 (مطابقة للصور) ====================

            # 1. Server 2019 Standard 2pc Retail Online (4 مفاتيح)
            desc_srv_std = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 Standard 2pc Retail Online', desc_srv_std, 2.80, '7 أيام', 'يدوي / manual'))
            p_s1 = cursor.lastrowid
            for i in range(4):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s1, f"SRV19-STD2P-KEY96-2639M-STD{i+1:02d}"))

            # 2. Server 2019 RDS Devices Connections (50) CAL (5 مفاتيح)
            desc_srv_rds_dev = """📝 يرجى ملاحظة أن هذا المفتاح يضيف تراخيص اتصال أجهزة ريموت ديسك توب (Device CAL وليس User CAL) إلى خادم Windows 2019 Server المفعل مسبقاً لديك. لا يمكن استخدامه لتفعيل نظام السيرفر نفسه."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 RDS Devices Connections (50) CAL', desc_srv_rds_dev, 3.30, '7 أيام', 'يدوي / manual'))
            p_s2 = cursor.lastrowid
            for i in range(5):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s2, f"SRV19-RDSDEV-50CAL-2639M-CAL{i+1:02d}"))

            # 3. Server 2019 RDS Users Connections (50) CAL (5 مفاتيح)
            desc_srv_rds_usr = """📝 يرجى ملاحظة أن هذا المفتاح يضيف تراخيص اتصال مستخدمين ريموت ديسك توب (User CAL وليس Device CAL) إلى خادم Windows 2019 Server المفعل مسبقاً لديك. لا يمكن استخدامه لتفعيل نظام السيرفر نفسه."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 RDS Users Connections (50) CAL', desc_srv_rds_usr, 3.30, '7 أيام', 'يدوي / manual'))
            p_s3 = cursor.lastrowid
            for i in range(5):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s3, f"SRV19-RDSUSR-50CAL-2639M-CAL{i+1:02d}"))

            # 4. Server 2019 Datacenter 2PC Retail Online (3 مفاتيح)
            desc_srv19_dc_ret = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 Datacenter 2PC Retail Online', desc_srv19_dc_ret, 1.80, '7 أيام', 'يدوي / manual'))
            p_s4 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s4, f"SRV19-DCRET-2PC96-2639M-DC{i+1:02d}"))

            # 5. Server 2019 Datacenter 1000PC [MAK:Volume] (3 مفاتيح)
            desc_srv19_dc_mak = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 Datacenter 1000PC [MAK:Volume]', desc_srv19_dc_mak, 9.50, '60 يوم', 'يدوي / manual'))
            p_s5 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s5, f"SRV19-DCMAK-1000P-2639M-MAK{i+1:02d}"))

            # 6. Server 2019 Standard 100PC [MAK:Volume] (3 مفاتيح)
            desc_srv19_std_mak = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2019'], 'Server 2019 Standard 100PC [MAK:Volume]', desc_srv19_std_mak, 9.50, '60 يوم', 'يدوي / manual'))
            p_s6 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s6, f"SRV19-STDMAK-100PC-2639M-MAK{i+1:02d}"))

            # ==================== منتجات Windows Server 2022 (مطابقة للصور) ====================

            # 1. Server 2022 Standard 2pc Retail Online (2 مفاتيح)
            desc_srv22_std = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 Standard 2pc Retail Online', desc_srv22_std, 3.70, '7 أيام', 'يدوي / manual'))
            p_s22_1 = cursor.lastrowid
            for i in range(2):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_1, f"SRV22-STD2P-KEY96-2639M-STD{i+1:02d}"))

            # 2. Server 2022 RDS User connections (50) CAL (مفتاح 1)
            desc_srv22_rds_usr = """📝 يرجى ملاحظة أن هذا المفتاح يضيف تراخيص اتصال مستخدمين ريموت ديسك توب (User CAL وليس Device CAL) إلى خادم Windows 2022 Server المفعل مسبقاً لديك. لا يمكن استخدامه لتفعيل نظام السيرفر نفسه."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 RDS User connections (50) CAL', desc_srv22_rds_usr, 12.00, '7 أيام', 'يدوي / manual'))
            p_s22_2 = cursor.lastrowid
            cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_2, "SRV22-RDSUSR-50CAL-2639M-CAL01"))

            # 3. Server 2022 RDS Device connections (50) CAL (5 مفاتيح)
            desc_srv22_rds_dev = """📝 يرجى ملاحظة أن هذا المفتاح يضيف تراخيص اتصال أجهزة ريموت ديسك توب (Device CAL وليس User CAL) إلى خادم Windows 2022 Server المفعل مسبقاً لديك. لا يمكن استخدامه لتفعيل نظام السيرفر نفسه."""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 RDS Device connections (50) CAL', desc_srv22_rds_dev, 6.50, '7 أيام', 'يدوي / manual'))
            p_s22_3 = cursor.lastrowid
            for i in range(5):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_3, f"SRV22-RDSDEV-50CAL-2639M-CAL{i+1:02d}"))

            # 4. Server 2022 Datacenter 2PC Retail Online (5 مفاتيح)
            desc_srv22_dc_ret = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 Datacenter 2PC Retail Online', desc_srv22_dc_ret, 3.00, '7 أيام', 'يدوي / manual'))
            p_s22_4 = cursor.lastrowid
            for i in range(5):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_4, f"SRV22-DCRET-2PC96-2639M-DC{i+1:02d}"))

            # 5. Server 2022 Datacenter VL-MAK 1000PC (3 مفاتيح)
            desc_srv22_dc_mak = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 Datacenter VL-MAK 1000PC', desc_srv22_dc_mak, 9.50, '60 يوم', 'يدوي / manual'))
            p_s22_5 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_5, f"SRV22-DCMAK-1000P-2639M-MAK{i+1:02d}"))

            # 6. Server 2022 Standard VL-MAK 100PC (3 مفاتيح)
            desc_srv22_std_mak = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2022'], 'Server 2022 Standard VL-MAK 100PC', desc_srv22_std_mak, 9.50, '60 يوم', 'يدوي / manual'))
            p_s22_6 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s22_6, f"SRV22-STDMAK-100PC-2639M-MAK{i+1:02d}"))

            # ==================== منتجات Windows Server 2025 ====================
            desc_srv25_std = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2025'], 'Server 2025 Standard 2pc Retail Online', desc_srv25_std, 4.50, '7 أيام', 'يدوي / manual'))
            p_s25_1 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s25_1, f"SRV25-STD2P-KEY96-2639M-STD{i+1:02d}"))

            desc_srv25_dc = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2025'], 'Server 2025 Datacenter 2PC Retail Online', desc_srv25_dc, 4.00, '7 أيام', 'يدوي / manual'))
            p_s25_2 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s25_2, f"SRV25-DCRET-2PC96-2639M-DC{i+1:02d}"))

            # ==================== منتجات Windows Server 2016 ====================
            desc_srv16_std = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerStandard /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2016'], 'Server 2016 Standard 2pc Retail Online', desc_srv16_std, 2.50, '7 أيام', 'يدوي / manual'))
            p_s16_1 = cursor.lastrowid
            for i in range(4):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s16_1, f"SRV16-STD2P-KEY96-2639M-STD{i+1:02d}"))

            desc_srv16_dc = """📝 للتحويل من نسخة التقييم (Evaluation) إلى النسخة الكاملة:
👉 افتح موجه الأوامر كمسؤول (Command Prompt as Administrator):
⭐ انقر بزر الماوس الأيمن على زر ابدأ واختر Command Prompt (Admin) أو Windows PowerShell (Admin).

👉 أدخل مفتاح المنتج:
⭐ قم بتشغيل الأمر التالي مع استبدال XXXXX-XXXXX-XXXXX-XXXXX-XXXXX بمفتاح المنتج الخاص بك:
`dism /online /set-edition:ServerDatacenter /productkey:XXXXX-XXXXX-XXXXX-XXXXX-XXXXX /accepteula`

أعد تشغيل السيرفر واتبع التعليمات لإعادة التشغيل. بعد إعادة التشغيل، سيتم تحويل ويندوز سيرفر إلى النسخة الكاملة.

روابط التحميل:
https://massgrave.dev/windows-server-links"""

            cursor.execute("""
                INSERT INTO products (subcategory_id, name, description, price, warranty, delivery)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subcat_ids['Microsoft Windows Server 2016'], 'Server 2016 Datacenter 2PC Retail Online', desc_srv16_dc, 1.60, '7 أيام', 'يدوي / manual'))
            p_s16_2 = cursor.lastrowid
            for i in range(3):
                cursor.execute("INSERT INTO product_items (product_id, item_content) VALUES (?, ?)", (p_s16_2, f"SRV16-DCRET-2PC96-2639M-DC{i+1:02d}"))

        conn.commit()

# ==================== دوال المستخدمين ====================

def get_or_create_user(telegram_id: int, username: str = "", first_name: str = "") -> sqlite3.Row:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute(
                "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
                (telegram_id, username or "", first_name or "")
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user = cursor.fetchone()
        else:
            cursor.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                (username or "", first_name or "", telegram_id)
            )
            conn.commit()
        return user

def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cursor.fetchone()

def update_user_balance(telegram_id: int, amount: float) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, telegram_id))
        conn.commit()
        return cursor.rowcount > 0

def set_user_balance(telegram_id: int, new_balance: float) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, telegram_id))
        conn.commit()
        return cursor.rowcount > 0

def get_all_users() -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id DESC")
        return cursor.fetchall()

# ==================== دوال الأقسام الرئيسية والفرعية ====================

def get_categories() -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories ORDER BY id ASC")
        return cursor.fetchall()

def get_category(category_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return cursor.fetchone()

def add_category(name: str) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return cursor.lastrowid

def delete_category(category_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_subcategories(category_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subcategories WHERE category_id = ? ORDER BY id ASC", (category_id,))
        return cursor.fetchall()

def get_subcategory(subcategory_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.name as category_name 
            FROM subcategories s 
            JOIN categories c ON s.category_id = c.id 
            WHERE s.id = ?
        """, (subcategory_id,))
        return cursor.fetchone()

def add_subcategory(category_id: int, name: str) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (category_id, name))
        conn.commit()
        return cursor.lastrowid

def delete_subcategory(subcategory_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subcategories WHERE id = ?", (subcategory_id,))
        conn.commit()
        return cursor.rowcount > 0

# ==================== دوال المنتجات والمخزون ====================

def get_products_by_subcategory(subcategory_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, 
            (SELECT COUNT(*) FROM product_items WHERE product_id = p.id AND is_sold = 0) as stock_count 
            FROM products p 
            WHERE p.subcategory_id = ? 
            ORDER BY p.id ASC
        """, (subcategory_id,))
        return cursor.fetchall()

def get_all_products() -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name as subcategory_name, c.name as category_name,
            (SELECT COUNT(*) FROM product_items WHERE product_id = p.id AND is_sold = 0) as stock_count 
            FROM products p 
            JOIN subcategories s ON p.subcategory_id = s.id
            JOIN categories c ON s.category_id = c.id
            ORDER BY p.id ASC
        """)
        return cursor.fetchall()

def get_product(product_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.name as subcategory_name, c.name as category_name,
            (SELECT COUNT(*) FROM product_items WHERE product_id = p.id AND is_sold = 0) as stock_count 
            FROM products p 
            JOIN subcategories s ON p.subcategory_id = s.id
            JOIN categories c ON s.category_id = c.id
            WHERE p.id = ?
        """, (product_id,))
        return cursor.fetchone()

def add_product(subcategory_id: int, name: str, description: str, price: float, warranty: str = "365 Days", delivery: str = "Instant") -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (subcategory_id, name, description, price, warranty, delivery) VALUES (?, ?, ?, ?, ?, ?)",
            (subcategory_id, name, description, price, warranty, delivery)
        )
        conn.commit()
        return cursor.lastrowid

def delete_product(product_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0

def add_product_items(product_id: int, items: List[str]) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        count = 0
        for item in items:
            item = item.strip()
            if item:
                cursor.execute(
                    "INSERT INTO product_items (product_id, item_content) VALUES (?, ?)",
                    (product_id, item)
                )
                count += 1
        conn.commit()
        return count

def get_available_stock_count(product_id: int) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM product_items WHERE product_id = ? AND is_sold = 0", (product_id,))
        return cursor.fetchone()[0]

# ==================== عملية الشراء ====================

def purchase_product(telegram_id: int, product_id: int, quantity: int = 1) -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        if not user:
            return {"success": False, "error": "المستخدم غير مسجل"}
            
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            return {"success": False, "error": "المنتج غير متوفر"}
            
        total_price = product["price"] * quantity
        if user["balance"] < total_price:
            return {"success": False, "error": "Not enough balance and BNPL is not enabled."}
            
        cursor.execute(
            "SELECT * FROM product_items WHERE product_id = ? AND is_sold = 0 LIMIT ?",
            (product_id, quantity)
        )
        items = cursor.fetchall()
        if len(items) < quantity:
            return {"success": False, "error": f"المخزون المتاح ({len(items)}) أقل من المطلوب ({quantity})"}
            
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # خصم الرصيد
        cursor.execute("UPDATE users SET balance = balance - ? WHERE telegram_id = ?", (total_price, telegram_id))
        
        # تسليم الأكواد
        delivered_keys = []
        for item in items:
            cursor.execute(
                "UPDATE product_items SET is_sold = 1, sold_to_user_id = ?, sold_at = ? WHERE id = ?",
                (user["id"], now, item["id"])
            )
            delivered_keys.append(item["item_content"])
            
        order_code = "ORD-" + uuid.uuid4().hex[:8].upper()
        keys_joined = "\n".join(delivered_keys)
        
        cursor.execute("""
            INSERT INTO orders (order_code, user_id, telegram_id, product_id, product_name, quantity, price, item_content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_code, user["id"], telegram_id, product["id"], product["name"], quantity, total_price, keys_joined, now))
        
        conn.commit()
        
        return {
            "success": True,
            "order_code": order_code,
            "product_name": product["name"],
            "quantity": quantity,
            "total_price": total_price,
            "keys": delivered_keys,
            "new_balance": user["balance"] - total_price,
            "created_at": now
        }

# ==================== دوال الطلبات والمشتريات ====================

def get_user_orders(telegram_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE telegram_id = ? ORDER BY id DESC", (telegram_id,))
        return cursor.fetchall()

def get_order_by_code(order_code: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,))
        return cursor.fetchone()

def get_all_orders() -> List[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100")
        return cursor.fetchall()

# ==================== دوال الإعدادات والطلبات ====================

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def normalize_trx_ref(ref: str) -> str:
    if not ref:
        return ""
    # تحويل الأرقام العربية والفارسية إلى أرقام إنجليزية موحدة
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    
    translation_table = str.maketrans(arabic_digits + persian_digits, english_digits + english_digits)
    cleaned = ref.strip().translate(translation_table)
    # إزالة الفراغات والرموز الشائعة لتفادي أي تحايل
    cleaned = cleaned.replace(" ", "").replace("-", "").replace("#", "").upper()
    return cleaned

def is_transaction_ref_exists(ref: str) -> bool:
    norm_ref = normalize_trx_ref(ref)
    if not norm_ref:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, transaction_ref FROM deposit_requests")
        rows = cursor.fetchall()
        for r in rows:
            existing = normalize_trx_ref(r["transaction_ref"] or "")
            if existing and existing == norm_ref:
                return True
        return False

def create_deposit_request(telegram_id: int, method: str, photo_id: str, transaction_ref: str, amount: float = 0.0) -> int:
    norm_ref = normalize_trx_ref(transaction_ref)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        user_id = user["id"] if user else 0
        
        cursor.execute("""
            INSERT INTO deposit_requests (user_id, telegram_id, amount, payment_method, receipt_photo_id, transaction_ref)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, telegram_id, amount, method, photo_id, norm_ref))
        conn.commit()
        return cursor.lastrowid

def get_deposit_request(request_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deposit_requests WHERE id = ?", (request_id,))
        return cursor.fetchone()

def update_deposit_status(request_id: int, status: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE deposit_requests SET status = ? WHERE id = ?", (status, request_id))
        conn.commit()
        return cursor.rowcount > 0

def approve_deposit_with_amount(request_id: int, approved_amount: float) -> Optional[dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deposit_requests WHERE id = ?", (request_id,))
        dep = cursor.fetchone()
        if not dep or dep["status"] != "pending":
            return None
        
        cursor.execute(
            "UPDATE deposit_requests SET status = 'approved', amount = ? WHERE id = ?",
            (approved_amount, request_id)
        )
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (approved_amount, dep["telegram_id"])
        )
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (dep["telegram_id"],))
        user = cursor.fetchone()
        conn.commit()
        return {
            "telegram_id": dep["telegram_id"],
            "amount": approved_amount,
            "new_balance": user["balance"] if user else approved_amount,
            "payment_method": dep["payment_method"],
            "transaction_ref": dep["transaction_ref"]
        }

init_db()
