# ==========================================================
#   DATABASE — bot va web API ikkalasi ham ishlatadi
#   SQLite ishlatadi (Railway'da Volume orqali persist bo'ladi)
# ==========================================================

import aiosqlite
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "/data/bot.db")

# Agar /data papkasi yo'q bo'lsa (lokalda test), shu yerga saqlaydi
if not os.path.exists(os.path.dirname(DB_PATH)) and DB_PATH.startswith("/data"):
    DB_PATH = "bot.db"


# ==========================================================
#   ASOSIY SETTINGS
# ==========================================================
DEFAULT_SETTINGS = {
    # Botning matn sozlamalari
    "welcome_text": "👋 Salom, <b>{name}</b>!\n\n⭐ Star va 💎 Premium sotib olish uchun pastdagi tugmalardan foydalaning.\n🌐 Yoki saytdan to'liq tajriba uchun: <a href='{webapp_url}'>Tezkor Star Web App</a>",
    "stars_menu_text": "⭐ <b>Star sotib olish</b>\n\nKerakli paketni tanlang:",
    "premium_menu_text": "💎 <b>Telegram Premium</b>\n\nMuddatni tanlang:",
    "help_text": "❓ <b>Yordam</b>\n\n👨‍💼 Admin: @{admin}\n⏰ 24/7 ishlaymiz",
    "about_text": "ℹ️ <b>Bot haqida</b>\n\n⭐ Telegram Star\n💎 Telegram Premium\n\n✅ Tez yetkazib beramiz\n✅ Ishonchli",
    "ask_username_text": "👤 <b>Kimga yuboramiz?</b>\n\nTelegram username yuboring (masalan: <code>@username</code>)\n\nYoki o'zingizga olayotgan bo'lsangiz, pastdagi <b>🔗 O'zimga</b> tugmasini bosing.",
    "payment_text": "💳 <b>TO'LOV MA'LUMOTLARI</b>\n\n💳 Karta: <code>{card}</code>\n🏦 Bank: {bank}\n👤 Egasi: {holder}\n\n💰 <b>Miqdor: {amount} so'm</b>\n\n⚠️ Tolov qilgandan keyin <b>chek rasmini</b> shu yerga yuboring.",
    "waiting_admin_text": "✅ <b>To'lov qabul qilindi!</b>\n\n⏱ <b>5 daqiqa</b> ichida hisobingizga tushadi.",
    "order_completed_text": "🎉 <b>Tabriklaymiz!</b>\n\n✅ Buyurtmangiz bajarildi.",
    "order_rejected_text": "❌ <b>Buyurtma rad etildi.</b>\n\nIltimos, admin bilan bog'laning: @{admin}",
    "sub_required_text": "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",

    # Tugma matnlari
    "btn_stars": "⭐ Star sotib olish",
    "btn_premium": "💎 Premium sotib olish",
    "btn_webapp": "🌐 Saytni ochish",
    "btn_help": "❓ Yordam",
    "btn_about": "ℹ️ Bot haqida",
    "btn_back": "◀️ Orqaga",
    "btn_cancel": "❌ Bekor qilish",
    "btn_main": "🏠 Asosiy menyu",
    "btn_contact_admin": "👨‍💼 Admin bilan bog'lanish",
    "btn_check_sub": "✅ Tekshirish",
    "btn_myself": "🔗 O'zimga",

    # To'lov ma'lumotlari
    "payment_card": "9860230102795708",
    "payment_bank": "Universalbank Humo",
    "payment_holder": "ADMIN",

    # Admin & web app
    "admin_username": "tezkor_admin",
    "webapp_url": "https://tezkor-star.vercel.app",

    # Star kursi (1 star = qancha so'm)
    "star_rate_uzs": "210",

    # ============ TO'LOV API SOZLAMALARI ============
    # Admin paneldan to'ldiriladi, bo'sh bo'lsa qo'lda tasdiqlash rejimi
    "payment_provider": "",         # "click" | "mirpay" | "" (bo'sh = qo'lda)
    "click_merchant_id": "",
    "click_service_id": "",
    "click_secret_key": "",
    "mirpay_merchant_id": "",
    "mirpay_api_key": "",
    "mirpay_secret": "",

    # Stikerlar/Video
    "welcome_sticker": "",
    "order_sticker": "",
    "success_sticker": "",
    "about_video": "",
    "proof_channel": "",
}

# Default Star paketlari (sonlar, narx hisoblanadi star_rate_uzs orqali)
DEFAULT_STAR_PACKAGES = [50, 100, 250, 500, 1000, 2500]
DEFAULT_PREMIUM_PACKAGES = [(3, 175000), (6, 235000), (12, 425000)]


# ==========================================================
#   INIT
# ==========================================================
async def init_db():
    """Database va barcha tablitsalarni yaratadi"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Users — kengaytirilgan (balans, referal, total_spent)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                photo_url TEXT,
                balance INTEGER DEFAULT 0,           -- UZS so'mda
                stars_bought INTEGER DEFAULT 0,      -- jami sotib olingan star
                total_spent INTEGER DEFAULT 0,       -- jami xarajat (UZS)
                referred_by INTEGER,                 -- kim taklif qilgan
                referral_count INTEGER DEFAULT 0,    -- nechta odam taklif qildi
                referral_earnings INTEGER DEFAULT 0, -- referal'lardan tushum
                is_admin INTEGER DEFAULT 0,          -- admin huquqi
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Star paketlari (faqat son, narx kursdan hisoblanadi)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS star_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stars INTEGER UNIQUE,
                custom_price INTEGER DEFAULT 0   -- 0 bo'lsa kursdan hisoblanadi
            )
        """)

        # Premium paketlari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS premium_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                months INTEGER UNIQUE,
                price INTEGER
            )
        """)

        # Orders — buyurtmalar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                order_type TEXT,           -- "stars" | "premium"
                package_info TEXT,         -- "100 stars" | "3 oy Premium"
                amount_value INTEGER,      -- star soni yoki premium oy
                price INTEGER,             -- UZS
                recipient TEXT,            -- @username
                status TEXT DEFAULT 'pending', -- pending|paid|completed|rejected
                payment_proof TEXT,        -- file_id
                source TEXT DEFAULT 'bot', -- bot|webapp
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        # Balance transactions — to'ldirishlar
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,                  -- topup|spend|refund|referral_bonus
                amount INTEGER,             -- + yoki -
                description TEXT,
                status TEXT DEFAULT 'pending', -- pending|completed|rejected
                payment_method TEXT,        -- manual|click|mirpay
                external_id TEXT,           -- click/mirpay tomonidagi ID
                proof_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Referrals — kim kimni taklif qilgan
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,        -- taklif qiluvchi
                referred_id INTEGER UNIQUE, -- taklif qilingan
                first_purchase_at TIMESTAMP,  -- birinchi xarid (faqat shundan keyin hisoblanadi)
                is_counted INTEGER DEFAULT 0, -- xarid qilganmi (1 bo'lsa hisoblangan)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Manual rating overrides — admin qo'lda 1-2-3 o'rinni o'zgartirsa
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rating_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rating_type TEXT,           -- spending_alltime|spending_week|spending_month|referral
                position INTEGER,           -- 1|2|3
                user_id INTEGER,
                custom_value INTEGER,       -- override qiymat
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(rating_type, position)
            )
        """)

        # Majburiy obuna kanallari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                channel_title TEXT
            )
        """)

        # Default settings
        for k, v in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v)
            )

        # Default Star paketlari
        cur = await db.execute("SELECT COUNT(*) FROM star_packages")
        if (await cur.fetchone())[0] == 0:
            for s in DEFAULT_STAR_PACKAGES:
                await db.execute("INSERT INTO star_packages (stars) VALUES (?)", (s,))

        # Default Premium paketlari
        cur = await db.execute("SELECT COUNT(*) FROM premium_packages")
        if (await cur.fetchone())[0] == 0:
            for m, p in DEFAULT_PREMIUM_PACKAGES:
                await db.execute("INSERT INTO premium_packages (months, price) VALUES (?, ?)", (m, p))

        await db.commit()


# ==========================================================
#   SETTINGS
# ==========================================================
async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        r = await cur.fetchone()
        return r[0] if r else ""

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_all_settings():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT key, value FROM settings")
        return dict(await cur.fetchall())


# ==========================================================
#   USERS
# ==========================================================
async def add_or_update_user(user_id, username=None, first_name=None, last_name=None, photo_url=None, referred_by=None):
    """User'ni qo'shadi yoki yangilaydi. Yangi bo'lsa referral'ni ham yozadi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        exists = await cur.fetchone()

        if exists:
            await db.execute("""
                UPDATE users SET username=?, first_name=?, last_name=?, photo_url=?, last_active=CURRENT_TIMESTAMP
                WHERE user_id=?
            """, (username, first_name, last_name, photo_url, user_id))
        else:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, photo_url, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, photo_url, referred_by))

            # Referral yozuvi
            if referred_by and referred_by != user_id:
                ref_cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (referred_by,))
                if await ref_cur.fetchone():
                    await db.execute("""
                        INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)
                    """, (referred_by, user_id))

        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]

async def update_balance(user_id, delta, description="", tx_type="manual", payment_method="manual"):
    """Balansni o'zgartiradi va tranzaksiya yozadi"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))
        await db.execute("""
            INSERT INTO transactions (user_id, type, amount, description, status, payment_method)
            VALUES (?, ?, ?, ?, 'completed', ?)
        """, (user_id, tx_type, delta, description, payment_method))
        await db.commit()

async def add_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def remove_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin=0 WHERE user_id=?", (user_id,))
        await db.commit()


# ==========================================================
#   STAR / PREMIUM PACKAGES
# ==========================================================
async def get_star_packages():
    """Star paketlarini qaytaradi, hozirgi kursdan narxni hisoblaydi"""
    rate = int(await get_setting("star_rate_uzs") or "210")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, stars, custom_price FROM star_packages ORDER BY stars")
        rows = await cur.fetchall()
        result = []
        for i, s, cp in rows:
            price = cp if cp > 0 else s * rate
            result.append({"id": i, "stars": s, "price": price})
        return result

async def add_star_package(stars, custom_price=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO star_packages (stars, custom_price) VALUES (?, ?)", (stars, custom_price))
        await db.commit()

async def delete_star_package(pid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM star_packages WHERE id=?", (pid,))
        await db.commit()

async def get_star_package(pid):
    rate = int(await get_setting("star_rate_uzs") or "210")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, stars, custom_price FROM star_packages WHERE id=?", (pid,))
        r = await cur.fetchone()
        if not r:
            return None
        price = r[2] if r[2] > 0 else r[1] * rate
        return {"id": r[0], "stars": r[1], "price": price}

async def get_premium_packages():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, months, price FROM premium_packages ORDER BY months")
        return [{"id": i, "months": m, "price": p} for i, m, p in await cur.fetchall()]

async def get_premium_package(pid):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, months, price FROM premium_packages WHERE id=?", (pid,))
        r = await cur.fetchone()
        return {"id": r[0], "months": r[1], "price": r[2]} if r else None

async def update_premium_price(pid, price):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE premium_packages SET price=? WHERE id=?", (price, pid))
        await db.commit()


# ==========================================================
#   ORDERS
# ==========================================================
async def create_order(user_id, order_type, package_info, amount_value, price, recipient, source="bot"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO orders (user_id, order_type, package_info, amount_value, price, recipient, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, order_type, package_info, amount_value, price, recipient, source))
        await db.commit()
        return cur.lastrowid

async def get_order(oid):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (oid,))
        r = await cur.fetchone()
        return dict(r) if r else None

async def get_user_orders(user_id, status=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cur = await db.execute(
                "SELECT * FROM orders WHERE user_id=? AND status=? ORDER BY created_at DESC LIMIT 50",
                (user_id, status)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (user_id,)
            )
        return [dict(r) for r in await cur.fetchall()]

async def update_order_status(oid, status, proof=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if proof:
            await db.execute("UPDATE orders SET status=?, payment_proof=? WHERE id=?", (status, proof, oid))
        else:
            if status == "completed":
                await db.execute("UPDATE orders SET status=?, completed_at=CURRENT_TIMESTAMP WHERE id=?", (status, oid))
            else:
                await db.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))

        # Agar tasdiqlangan bo'lsa — user statistikasi yangilanadi
        if status == "completed":
            cur = await db.execute("SELECT user_id, price, order_type, amount_value FROM orders WHERE id=?", (oid,))
            r = await cur.fetchone()
            if r:
                uid, price, otype, amt = r
                await db.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id=?", (price, uid))
                if otype == "stars":
                    await db.execute("UPDATE users SET stars_bought = stars_bought + ? WHERE user_id=?", (amt, uid))

                # Referal hisobi (faqat birinchi xarid)
                ref_cur = await db.execute(
                    "SELECT id, referrer_id, is_counted FROM referrals WHERE referred_id=?", (uid,)
                )
                ref = await ref_cur.fetchone()
                if ref and ref[2] == 0 and otype == "stars":
                    ref_id, referrer_id, _ = ref
                    await db.execute(
                        "UPDATE referrals SET is_counted=1, first_purchase_at=CURRENT_TIMESTAMP WHERE id=?",
                        (ref_id,)
                    )
                    await db.execute(
                        "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?",
                        (referrer_id,)
                    )

        await db.commit()


# ==========================================================
#   TRANSACTIONS (balansga to'ldirish)
# ==========================================================
async def create_topup_request(user_id, amount, payment_method="manual", proof_file_id=None, external_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO transactions (user_id, type, amount, description, status, payment_method, proof_file_id, external_id)
            VALUES (?, 'topup', ?, ?, 'pending', ?, ?, ?)
        """, (user_id, amount, f"Balansga to'ldirish {amount} so'm", payment_method, proof_file_id, external_id))
        await db.commit()
        return cur.lastrowid

async def approve_topup(tx_id):
    """Topup tasdiqlash — balansga qo'shadi"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, amount, status FROM transactions WHERE id=?", (tx_id,))
        r = await cur.fetchone()
        if not r or r[2] != 'pending':
            return False
        uid, amount, _ = r
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
        await db.execute("UPDATE transactions SET status='completed' WHERE id=?", (tx_id,))
        await db.commit()
        return True

async def reject_topup(tx_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE transactions SET status='rejected' WHERE id=?", (tx_id,))
        await db.commit()

async def get_user_transactions(user_id, limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return [dict(r) for r in await cur.fetchall()]


# ==========================================================
#   RATINGS
# ==========================================================
async def get_rating_spending(period="alltime"):
    """Sotib oluvchilar reytingi. period: alltime | month | week"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Avval admin override'larini olamiz
        override_cur = await db.execute(
            "SELECT position, user_id, custom_value FROM rating_overrides WHERE rating_type=?",
            (f"spending_{period}",)
        )
        overrides = {p: (uid, val) for p, uid, val in await override_cur.fetchall()}

        if period == "alltime":
            cur = await db.execute("""
                SELECT u.user_id, u.username, u.first_name, u.photo_url, u.total_spent as value, u.stars_bought
                FROM users u
                WHERE u.total_spent > 0
                ORDER BY u.total_spent DESC
                LIMIT 20
            """)
        else:
            interval = "-7 days" if period == "week" else "-30 days"
            cur = await db.execute(f"""
                SELECT u.user_id, u.username, u.first_name, u.photo_url,
                       COALESCE(SUM(o.price), 0) as value,
                       COALESCE(SUM(CASE WHEN o.order_type='stars' THEN o.amount_value ELSE 0 END), 0) as stars_bought
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id
                    AND o.status='completed'
                    AND o.completed_at >= datetime('now', '{interval}')
                GROUP BY u.user_id
                HAVING value > 0
                ORDER BY value DESC
                LIMIT 20
            """)
        results = [dict(r) for r in await cur.fetchall()]

        # Override'larni qo'llash
        for pos, (uid, val) in overrides.items():
            user_cur = await db.execute("SELECT user_id, username, first_name, photo_url FROM users WHERE user_id=?", (uid,))
            u = await user_cur.fetchone()
            if u:
                results = [r for r in results if r["user_id"] != uid]
                results.insert(pos - 1, {
                    "user_id": u[0], "username": u[1], "first_name": u[2],
                    "photo_url": u[3], "value": val, "stars_bought": 0, "is_override": True
                })

        return results[:20]

async def get_rating_referrals():
    """Referal'lar bo'yicha reyting"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        override_cur = await db.execute(
            "SELECT position, user_id, custom_value FROM rating_overrides WHERE rating_type='referral'"
        )
        overrides = {p: (uid, val) for p, uid, val in await override_cur.fetchall()}

        cur = await db.execute("""
            SELECT u.user_id, u.username, u.first_name, u.photo_url, u.referral_count as value,
                   COALESCE(SUM(o.price), 0) as ref_spending
            FROM users u
            LEFT JOIN referrals r ON r.referrer_id = u.user_id AND r.is_counted=1
            LEFT JOIN orders o ON o.user_id = r.referred_id AND o.status='completed'
            WHERE u.referral_count > 0
            GROUP BY u.user_id
            ORDER BY u.referral_count DESC, ref_spending DESC
            LIMIT 20
        """)
        results = [dict(r) for r in await cur.fetchall()]

        for pos, (uid, val) in overrides.items():
            user_cur = await db.execute("SELECT user_id, username, first_name, photo_url FROM users WHERE user_id=?", (uid,))
            u = await user_cur.fetchone()
            if u:
                results = [r for r in results if r["user_id"] != uid]
                results.insert(pos - 1, {
                    "user_id": u[0], "username": u[1], "first_name": u[2],
                    "photo_url": u[3], "value": val, "ref_spending": 0, "is_override": True
                })

        return results[:20]

async def set_rating_override(rating_type, position, user_id, custom_value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO rating_overrides (rating_type, position, user_id, custom_value)
            VALUES (?, ?, ?, ?)
        """, (rating_type, position, user_id, custom_value))
        await db.commit()

async def remove_rating_override(rating_type, position):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM rating_overrides WHERE rating_type=? AND position=?",
            (rating_type, position)
        )
        await db.commit()


# ==========================================================
#   CHANNELS
# ==========================================================
async def get_required_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, channel_id, channel_title FROM required_channels ORDER BY id")
        return await cur.fetchall()

async def add_required_channel(channel_id, title):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO required_channels (channel_id, channel_title) VALUES (?, ?)", (channel_id, title))
        await db.commit()

async def remove_required_channel(cid):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM required_channels WHERE id=?", (cid,))
        await db.commit()


# ==========================================================
#   STATS
# ==========================================================
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        r = {}
        queries = {
            "users": "SELECT COUNT(*) FROM users",
            "orders": "SELECT COUNT(*) FROM orders",
            "completed": "SELECT COUNT(*) FROM orders WHERE status='completed'",
            "pending": "SELECT COUNT(*) FROM orders WHERE status='paid'",
            "revenue": "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='completed'",
            "stars_sold": "SELECT COALESCE(SUM(amount_value),0) FROM orders WHERE status='completed' AND order_type='stars'",
        }
        for k, q in queries.items():
            cur = await db.execute(q)
            r[k] = (await cur.fetchone())[0]
        return r
