# ==========================================================
#   WEB API (FastAPI) — Telegram Mini App uchun
#   Bot bilan bir xil database'ni ishlatadi
# ==========================================================

import hashlib
import hmac
import json
import os
import time
from urllib.parse import unquote
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712600970:AAFFXIwrY1Rg_sVj4GrxXkMaqgEFSh0-J38")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8135915671"))

app = FastAPI(title="Tezkor Star API", version="1.0.0")

# CORS — Vercel'dan kelishi uchun
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da aniq domen qo'yish kerak
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
#   TELEGRAM WEBAPP INIT_DATA VERIFY
# ==========================================================
def verify_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Telegram WebApp initData'ni tekshiradi.
    Bo'sh stringga ham javob bermaydi (xavfsiz).
    """
    if not init_data:
        return None

    try:
        # Parse query string format: key1=val1&key2=val2
        parsed = {}
        for pair in init_data.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                parsed[k] = unquote(v)

        if "hash" not in parsed:
            return None

        received_hash = parsed.pop("hash")

        # Data-check-string yaratish
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        # Secret key = HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()

        # Calculated hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # Check freshness (24 soat)
        auth_date = int(parsed.get("auth_date", "0"))
        if time.time() - auth_date > 86400:
            return None

        # User'ni parse qilish
        user_str = parsed.get("user")
        if not user_str:
            return None

        user = json.loads(user_str)
        return {
            "user": user,
            "start_param": parsed.get("start_param"),
            "auth_date": auth_date,
        }
    except Exception as e:
        print(f"verify_telegram_init_data error: {e}")
        return None


async def get_current_user(x_init_data: str = Header(None, alias="X-Init-Data")) -> dict:
    """Dependency — har bir so'rovda Telegram user'ni tekshiradi"""
    if not x_init_data:
        raise HTTPException(401, "X-Init-Data header missing")

    data = verify_telegram_init_data(x_init_data)
    if not data:
        raise HTTPException(401, "Invalid init data")

    tg_user = data["user"]
    user_id = tg_user["id"]

    # Foydalanuvchini database'da yangilash
    referred_by = None
    if data.get("start_param"):
        try:
            sp = data["start_param"]
            if sp.startswith("ref_"):
                referred_by = int(sp[4:])
            else:
                referred_by = int(sp)
        except (ValueError, TypeError):
            pass

    await db.add_or_update_user(
        user_id,
        username=tg_user.get("username"),
        first_name=tg_user.get("first_name"),
        last_name=tg_user.get("last_name"),
        photo_url=tg_user.get("photo_url"),
        referred_by=referred_by,
    )

    user = await db.get_user(user_id)
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Admin huquqini tekshiradi"""
    if user["user_id"] != ADMIN_ID and not user.get("is_admin"):
        raise HTTPException(403, "Admin only")
    return user


# ==========================================================
#   STARTUP
# ==========================================================
@app.on_event("startup")
async def on_startup():
    await db.init_db()


# ==========================================================
#   PUBLIC ENDPOINTS
# ==========================================================
@app.get("/")
async def root():
    return {"status": "ok", "service": "Tezkor Star API"}


@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    """Hozirgi foydalanuvchi ma'lumotlari"""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "photo_url": user["photo_url"],
        "balance": user["balance"],
        "stars_bought": user["stars_bought"],
        "total_spent": user["total_spent"],
        "referral_count": user["referral_count"],
        "is_admin": bool(user.get("is_admin")) or user["user_id"] == ADMIN_ID,
    }


@app.get("/api/settings/public")
async def public_settings():
    """Hammaga ko'rinadigan sozlamalar"""
    keys = [
        "star_rate_uzs", "payment_card", "payment_bank", "payment_holder",
        "admin_username", "welcome_text", "about_text", "help_text", "webapp_url",
    ]
    result = {}
    for k in keys:
        result[k] = await db.get_setting(k)
    return result


@app.get("/api/packages/stars")
async def packages_stars():
    return await db.get_star_packages()


@app.get("/api/packages/premium")
async def packages_premium():
    return await db.get_premium_packages()


# ==========================================================
#   ORDERS
# ==========================================================
class BuyStarsBody(BaseModel):
    package_id: int
    recipient: str

class BuyPremiumBody(BaseModel):
    package_id: int
    recipient: str


@app.post("/api/buy/stars")
async def buy_stars(body: BuyStarsBody, user: dict = Depends(get_current_user)):
    pk = await db.get_star_package(body.package_id)
    if not pk:
        raise HTTPException(404, "Package not found")

    recipient = body.recipient.strip()
    if not recipient.startswith("@"):
        recipient = "@" + recipient.lstrip("@")
    if len(recipient) < 3 or " " in recipient:
        raise HTTPException(400, "Invalid recipient")

    if user["balance"] < pk["price"]:
        raise HTTPException(400, f"Mablag' yetarli emas. Kerak: {pk['price']:,} UZS, sizda: {user['balance']:,} UZS")

    # Balansdan yechib, order yaratamiz
    await db.update_balance(user["user_id"], -pk["price"], f"Star xaridi: {pk['stars']}", tx_type="spend")
    oid = await db.create_order(
        user["user_id"], "stars",
        f"⭐ {pk['stars']} star",
        pk["stars"], pk["price"], recipient, source="webapp"
    )
    # Avtomatik "paid" qo'yamiz (balans yechib olingan), admin starlarni jo'natishi kerak
    await db.update_order_status(oid, "paid")

    return {"order_id": oid, "status": "paid", "message": "Buyurtma qabul qilindi"}


@app.post("/api/buy/premium")
async def buy_premium(body: BuyPremiumBody, user: dict = Depends(get_current_user)):
    pk = await db.get_premium_package(body.package_id)
    if not pk:
        raise HTTPException(404, "Package not found")

    recipient = body.recipient.strip()
    if not recipient.startswith("@"):
        recipient = "@" + recipient.lstrip("@")
    if len(recipient) < 3 or " " in recipient:
        raise HTTPException(400, "Invalid recipient")

    if user["balance"] < pk["price"]:
        raise HTTPException(400, f"Mablag' yetarli emas. Kerak: {pk['price']:,} UZS, sizda: {user['balance']:,} UZS")

    await db.update_balance(user["user_id"], -pk["price"], f"Premium xaridi: {pk['months']} oy", tx_type="spend")
    oid = await db.create_order(
        user["user_id"], "premium",
        f"💎 {pk['months']} oy Premium",
        pk["months"], pk["price"], recipient, source="webapp"
    )
    await db.update_order_status(oid, "paid")

    return {"order_id": oid, "status": "paid", "message": "Buyurtma qabul qilindi"}


@app.get("/api/orders")
async def get_orders(user: dict = Depends(get_current_user), status: Optional[str] = None):
    return await db.get_user_orders(user["user_id"], status=status)


# ==========================================================
#   BALANCE TOP-UP
# ==========================================================
class TopupBody(BaseModel):
    amount: int
    method: str = "manual"  # "manual" | "click" | "mirpay"

@app.post("/api/topup/request")
async def request_topup(body: TopupBody, user: dict = Depends(get_current_user)):
    if body.amount <= 0 or body.amount > 50_000_000:
        raise HTTPException(400, "Invalid amount")

    provider = await db.get_setting("payment_provider")

    if body.method == "manual" or not provider:
        # Qo'lda — admin tasdiqlaydi
        tx_id = await db.create_topup_request(user["user_id"], body.amount, payment_method="manual")
        return {
            "tx_id": tx_id,
            "method": "manual",
            "instructions": {
                "card": await db.get_setting("payment_card"),
                "bank": await db.get_setting("payment_bank"),
                "holder": await db.get_setting("payment_holder"),
                "amount": body.amount,
                "message": "Karta orqali to'lab, chek rasmini botga yuboring",
            }
        }

    # Click/Mirpay — keyinroq amalga oshiriladi (placeholder)
    if body.method == "click":
        # TODO: Click invoice URL yaratish
        tx_id = await db.create_topup_request(user["user_id"], body.amount, payment_method="click")
        return {
            "tx_id": tx_id,
            "method": "click",
            "payment_url": "https://click.uz/pay/...",  # placeholder
            "message": "Click sahifasiga o'ting"
        }
    elif body.method == "mirpay":
        tx_id = await db.create_topup_request(user["user_id"], body.amount, payment_method="mirpay")
        return {
            "tx_id": tx_id,
            "method": "mirpay",
            "payment_url": "https://mirpay.uz/pay/...",  # placeholder
            "message": "Mirpay sahifasiga o'ting"
        }

    raise HTTPException(400, "Unknown method")


@app.get("/api/transactions")
async def get_transactions(user: dict = Depends(get_current_user)):
    return await db.get_user_transactions(user["user_id"])


# ==========================================================
#   RATINGS
# ==========================================================
@app.get("/api/ratings/spending")
async def rating_spending(period: str = "alltime"):
    """period: alltime | week | month"""
    if period not in ("alltime", "week", "month"):
        raise HTTPException(400, "Invalid period")
    return await db.get_rating_spending(period)


@app.get("/api/ratings/referrals")
async def rating_referrals():
    return await db.get_rating_referrals()


# ==========================================================
#   ADMIN ENDPOINTS
# ==========================================================
@app.get("/api/admin/stats")
async def admin_stats(_: dict = Depends(require_admin)):
    return await db.get_stats()


@app.get("/api/admin/settings")
async def admin_get_settings(_: dict = Depends(require_admin)):
    return await db.get_all_settings()


class SettingUpdate(BaseModel):
    key: str
    value: str

@app.post("/api/admin/settings")
async def admin_set_setting(body: SettingUpdate, _: dict = Depends(require_admin)):
    await db.set_setting(body.key, body.value)
    return {"ok": True}


class BalanceAdjust(BaseModel):
    user_id: int
    amount: int  # + yoki -
    description: str = "Admin tomonidan"

@app.post("/api/admin/balance")
async def admin_adjust_balance(body: BalanceAdjust, _: dict = Depends(require_admin)):
    user = await db.get_user(body.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    await db.update_balance(body.user_id, body.amount, body.description, tx_type="manual", payment_method="admin")
    new_user = await db.get_user(body.user_id)
    return {"ok": True, "new_balance": new_user["balance"]}


class TopupApproval(BaseModel):
    tx_id: int

@app.post("/api/admin/topup/approve")
async def admin_approve_topup(body: TopupApproval, _: dict = Depends(require_admin)):
    ok = await db.approve_topup(body.tx_id)
    if not ok:
        raise HTTPException(400, "Cannot approve")
    return {"ok": True}

@app.post("/api/admin/topup/reject")
async def admin_reject_topup(body: TopupApproval, _: dict = Depends(require_admin)):
    await db.reject_topup(body.tx_id)
    return {"ok": True}


class OrderAction(BaseModel):
    order_id: int

@app.post("/api/admin/order/approve")
async def admin_approve_order(body: OrderAction, _: dict = Depends(require_admin)):
    await db.update_order_status(body.order_id, "completed")
    return {"ok": True}

@app.post("/api/admin/order/reject")
async def admin_reject_order(body: OrderAction, _: dict = Depends(require_admin)):
    # Bekor qilinsa, balansga qaytarib beramiz
    order = await db.get_order(body.order_id)
    if order and order["status"] in ("paid", "pending"):
        await db.update_balance(order["user_id"], order["price"], f"Order #{body.order_id} bekor qilindi", tx_type="refund")
    await db.update_order_status(body.order_id, "rejected")
    return {"ok": True}


class RatingOverride(BaseModel):
    rating_type: str  # spending_alltime | spending_week | spending_month | referral
    position: int     # 1 | 2 | 3
    user_id: int
    custom_value: int

@app.post("/api/admin/rating/override")
async def admin_rating_override(body: RatingOverride, _: dict = Depends(require_admin)):
    if body.rating_type not in ("spending_alltime", "spending_week", "spending_month", "referral"):
        raise HTTPException(400, "Invalid rating_type")
    if body.position not in (1, 2, 3):
        raise HTTPException(400, "Position must be 1, 2 or 3")
    await db.set_rating_override(body.rating_type, body.position, body.user_id, body.custom_value)
    return {"ok": True}

@app.delete("/api/admin/rating/override")
async def admin_remove_rating_override(rating_type: str, position: int, _: dict = Depends(require_admin)):
    await db.remove_rating_override(rating_type, position)
    return {"ok": True}


class AdminAdd(BaseModel):
    user_id: int

@app.post("/api/admin/admins/add")
async def admin_add(body: AdminAdd, _: dict = Depends(require_admin)):
    user = await db.get_user(body.user_id)
    if not user:
        raise HTTPException(404, "User not found")
    await db.add_admin(body.user_id)
    return {"ok": True}

@app.post("/api/admin/admins/remove")
async def admin_remove(body: AdminAdd, current: dict = Depends(require_admin)):
    if current["user_id"] != ADMIN_ID:
        raise HTTPException(403, "Only main admin can remove admins")
    await db.remove_admin(body.user_id)
    return {"ok": True}


# ==========================================================
#   STAR/PREMIUM CRUD (admin)
# ==========================================================
class StarPackageCreate(BaseModel):
    stars: int
    custom_price: int = 0

@app.post("/api/admin/packages/stars")
async def admin_add_star(body: StarPackageCreate, _: dict = Depends(require_admin)):
    await db.add_star_package(body.stars, body.custom_price)
    return {"ok": True}

@app.delete("/api/admin/packages/stars/{pid}")
async def admin_del_star(pid: int, _: dict = Depends(require_admin)):
    await db.delete_star_package(pid)
    return {"ok": True}


class PremiumUpdate(BaseModel):
    price: int

@app.put("/api/admin/packages/premium/{pid}")
async def admin_upd_premium(pid: int, body: PremiumUpdate, _: dict = Depends(require_admin)):
    await db.update_premium_price(pid, body.price)
    return {"ok": True}
