# ==========================================================
#   TEZKOR STAR BOT — Telegram Bot
#   Asos: sening kodingdan moslangan. NFT olib tashlandi.
#   Web App bilan ulangan database.py orqali.
# ==========================================================

import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    CopyTextButton, WebAppInfo
)

import database as db

# ==========================================================
#   KONFIG — env variables (Railway/local)
# ==========================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712600970:AAFFXIwrY1Rg_sVj4GrxXkMaqgEFSh0-J38")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8135915671"))
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://tezkor-star.vercel.app")

# ==========================================================
EDITABLE_TEXTS = {
    "welcome_text": "👋 Salomlashuv",
    "stars_menu_text": "⭐ Star menyu",
    "premium_menu_text": "💎 Premium menyu",
    "help_text": "❓ Yordam",
    "about_text": "ℹ️ Bot haqida",
    "ask_username_text": "👤 Username so'rash",
    "payment_text": "💳 To'lov",
    "waiting_admin_text": "⏳ Kutish (5 daqiqa)",
    "order_completed_text": "🎉 Bajarildi",
    "order_rejected_text": "❌ Rad etildi",
    "sub_required_text": "⚠️ Obuna talab",
}

BTN_KEYS = {
    "btn_stars": "⭐ Star",
    "btn_premium": "💎 Premium",
    "btn_webapp": "🌐 Sayt",
    "btn_help": "❓ Yordam",
    "btn_about": "ℹ️ Bot haqida",
    "btn_back": "◀️ Orqaga",
    "btn_cancel": "❌ Bekor",
    "btn_main": "🏠 Menyu",
    "btn_contact_admin": "👨‍💼 Admin",
    "btn_check_sub": "✅ Tekshirish",
    "btn_myself": "🔗 O'zimga",
}

STICKER_SLOTS = {
    "welcome_sticker": "👋 Salomlashuv",
    "order_sticker": "📦 Buyurtma",
    "success_sticker": "🎉 Muvaffaqiyat",
}


# ==========================================================
#   HELPERS
# ==========================================================
async def fmt(key, **kw):
    """Matnni o'zgaruvchilar bilan formatlash"""
    t = await db.get_setting(key)
    kw.setdefault("admin", (await db.get_setting("admin_username")).lstrip("@") or "admin")
    kw.setdefault("webapp_url", await db.get_setting("webapp_url") or WEBAPP_URL)
    for k, v in kw.items():
        t = t.replace("{" + k + "}", str(v))
    return t

async def is_admin(user_id):
    """Asosiy admin yoki users.is_admin=1 bo'lsa True"""
    if user_id == ADMIN_ID:
        return True
    u = await db.get_user(user_id)
    return bool(u and u.get("is_admin"))

async def try_sticker(bot, chat_id, key):
    fid = await db.get_setting(key)
    if fid:
        with suppress(Exception):
            await bot.send_sticker(chat_id, fid)

async def safe_edit(call, text, kb, bot):
    try:
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except TelegramBadRequest:
        with suppress(Exception):
            await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, disable_web_page_preview=True)


# ==========================================================
#   OBUNA TEKSHIRUVI
# ==========================================================
async def check_sub(bot, uid):
    chs = await db.get_required_channels()
    bad = []
    for cid, ch_id, title in chs:
        try:
            m = await bot.get_chat_member(ch_id, uid)
            if m.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                bad.append((ch_id, title))
        except Exception:
            pass
    return bad

async def kb_sub_wall(bad):
    rows = []
    for ch_id, title in bad:
        url = f"https://t.me/{ch_id.lstrip('@')}" if ch_id.startswith("@") else f"https://t.me/c/{str(ch_id).replace('-100','')}"
        rows.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])
    rows.append([InlineKeyboardButton(text=await db.get_setting("btn_check_sub"), callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ==========================================================
#   STATES
# ==========================================================
class OrderFSM(StatesGroup):
    waiting_recipient = State()
    waiting_payment = State()
    waiting_topup_amount = State()
    waiting_topup_proof = State()

class AdminFSM(StatesGroup):
    editing_text = State()
    editing_button = State()
    adding_star_count = State()
    editing_star_price = State()
    adding_premium_months = State()
    adding_premium_price = State()
    editing_premium_price = State()
    editing_payment_info = State()
    editing_admin_username = State()
    editing_star_rate = State()
    setting_sticker = State()
    setting_about_video = State()
    setting_proof_channel = State()
    adding_channel_id = State()
    adding_channel_title = State()
    setting_payment_provider = State()
    editing_payment_api_key = State()
    adding_new_admin = State()
    adjust_balance = State()
    set_rating_override = State()
    broadcasting = State()


# ==========================================================
#   KEYBOARDS (USER)
# ==========================================================
async def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await db.get_setting("btn_webapp"),
            web_app=WebAppInfo(url=await db.get_setting("webapp_url") or WEBAPP_URL)
        )],
        [InlineKeyboardButton(text=await db.get_setting("btn_stars"), callback_data="menu:stars")],
        [InlineKeyboardButton(text=await db.get_setting("btn_premium"), callback_data="menu:premium")],
        [
            InlineKeyboardButton(text=await db.get_setting("btn_help"), callback_data="menu:help"),
            InlineKeyboardButton(text=await db.get_setting("btn_about"), callback_data="menu:about"),
        ],
    ])

async def kb_stars_list():
    pkgs = await db.get_star_packages()
    rows = []
    row = []
    for p in pkgs:
        btn = InlineKeyboardButton(
            text=f"⭐ {p['stars']} — {p['price']:,} so'm",
            callback_data=f"buy:stars:{p['id']}"
        )
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=await db.get_setting("btn_back"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def kb_premium_list():
    pkgs = await db.get_premium_packages()
    rows = [[InlineKeyboardButton(
        text=f"💎 {p['months']} oy — {p['price']:,} so'm",
        callback_data=f"buy:premium:{p['id']}"
    )] for p in pkgs]
    rows.append([InlineKeyboardButton(text=await db.get_setting("btn_back"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def kb_ask_username():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await db.get_setting("btn_myself"), callback_data="username:myself")],
        [InlineKeyboardButton(text=await db.get_setting("btn_cancel"), callback_data="order:cancel")],
    ])

async def kb_back_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await db.get_setting("btn_main"), callback_data="menu:main")]
    ])

async def kb_help():
    admin_un = (await db.get_setting("admin_username")).lstrip("@")
    rows = []
    if admin_un and admin_un != "username":
        rows.append([InlineKeyboardButton(text=await db.get_setting("btn_contact_admin"), url=f"https://t.me/{admin_un}")])
    rows.append([InlineKeyboardButton(text=await db.get_setting("btn_main"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def kb_pay_copy(card, amount):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Karta raqamini nusxalash", copy_text=CopyTextButton(text=card))],
        [InlineKeyboardButton(text="📋 Summani nusxalash", copy_text=CopyTextButton(text=amount))],
        [InlineKeyboardButton(text=await db.get_setting("btn_cancel"), callback_data="order:cancel")],
    ])


# ==========================================================
#   KEYBOARDS (ADMIN)
# ==========================================================
def kb_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Star paketlar", callback_data="a:stars"),
            InlineKeyboardButton(text="💎 Premium", callback_data="a:premium"),
        ],
        [
            InlineKeyboardButton(text="💱 Star kursi", callback_data="a:star_rate"),
            InlineKeyboardButton(text="💳 To'lov karta", callback_data="a:payment"),
        ],
        [
            InlineKeyboardButton(text="🔌 To'lov API", callback_data="a:payment_api"),
            InlineKeyboardButton(text="👨‍💼 Admin username", callback_data="a:username"),
        ],
        [
            InlineKeyboardButton(text="📝 Matnlar", callback_data="a:texts"),
            InlineKeyboardButton(text="🔘 Tugma nomlari", callback_data="a:buttons"),
        ],
        [
            InlineKeyboardButton(text="🎨 Stikerlar", callback_data="a:stickers"),
            InlineKeyboardButton(text="🎥 Bot video", callback_data="a:about_video"),
        ],
        [
            InlineKeyboardButton(text="📢 Tolovlar kanali", callback_data="a:proof_ch"),
            InlineKeyboardButton(text="📌 Majburiy obuna", callback_data="a:req_ch"),
        ],
        [
            InlineKeyboardButton(text="🏆 Reyting boshqaruvi", callback_data="a:ratings"),
            InlineKeyboardButton(text="👥 Adminlar", callback_data="a:admins"),
        ],
        [
            InlineKeyboardButton(text="💰 Foydalanuvchi balansi", callback_data="a:user_balance"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="a:broadcast"),
        ],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="a:stats")],
    ])

def kb_back_admin():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")]])

def kb_cancel(cb):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor", callback_data=cb)]])


# ==========================================================
#   ROUTERS
# ==========================================================
user_router = Router()
admin_router = Router()


# ==========================================================
#   USER HANDLERS
# ==========================================================
@user_router.message(CommandStart())
async def cmd_start(msg: Message, command: CommandObject, state: FSMContext, bot: Bot):
    await state.clear()

    # Referral parametrini olish (/start ref_12345)
    referred_by = None
    if command.args:
        try:
            if command.args.startswith("ref_"):
                referred_by = int(command.args[4:])
            else:
                referred_by = int(command.args)
        except ValueError:
            pass

    await db.add_or_update_user(
        msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
        referred_by=referred_by,
    )

    bad = await check_sub(bot, msg.from_user.id)
    if bad:
        return await msg.answer(await fmt("sub_required_text"), reply_markup=await kb_sub_wall(bad))

    await try_sticker(bot, msg.chat.id, "welcome_sticker")
    await msg.answer(
        await fmt("welcome_text", name=msg.from_user.first_name or "do'st"),
        reply_markup=await kb_main(),
        disable_web_page_preview=True,
    )

@user_router.callback_query(F.data == "check_sub")
async def cb_check(call: CallbackQuery, bot: Bot):
    bad = await check_sub(bot, call.from_user.id)
    if bad:
        await call.answer("❌ Hali obuna emas!", show_alert=True)
        return await safe_edit(call, await fmt("sub_required_text"), await kb_sub_wall(bad), bot)
    await call.answer("✅")
    await try_sticker(bot, call.message.chat.id, "welcome_sticker")
    await safe_edit(call, await fmt("welcome_text", name=call.from_user.first_name or "do'st"), await kb_main(), bot)

@user_router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    bad = await check_sub(bot, call.from_user.id)
    if bad:
        await safe_edit(call, await fmt("sub_required_text"), await kb_sub_wall(bad), bot)
        return await call.answer()
    await safe_edit(call, await fmt("welcome_text", name=call.from_user.first_name or "do'st"), await kb_main(), bot)
    await call.answer()

@user_router.callback_query(F.data == "menu:stars")
async def cb_stars(call: CallbackQuery, bot: Bot):
    await safe_edit(call, await fmt("stars_menu_text"), await kb_stars_list(), bot)
    await call.answer()

@user_router.callback_query(F.data == "menu:premium")
async def cb_prem(call: CallbackQuery, bot: Bot):
    await safe_edit(call, await fmt("premium_menu_text"), await kb_premium_list(), bot)
    await call.answer()

@user_router.callback_query(F.data == "menu:help")
async def cb_help(call: CallbackQuery, bot: Bot):
    await safe_edit(call, await fmt("help_text"), await kb_help(), bot)
    await call.answer()

@user_router.callback_query(F.data == "menu:about")
async def cb_about(call: CallbackQuery, bot: Bot):
    t = await fmt("about_text")
    vid = await db.get_setting("about_video")
    kb = await kb_back_main()
    if vid:
        with suppress(Exception):
            await call.message.delete()
        try:
            await bot.send_video(call.message.chat.id, vid, caption=t, reply_markup=kb)
        except Exception:
            await bot.send_message(call.message.chat.id, t, reply_markup=kb)
    else:
        await safe_edit(call, t, kb, bot)
    await call.answer()

@user_router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery, state: FSMContext):
    _, ot, pid = call.data.split(":")
    pid = int(pid)

    if ot == "stars":
        pk = await db.get_star_package(pid)
        if not pk:
            return await call.answer("❌", show_alert=True)
        info = f"⭐ {pk['stars']} star"
        amt_val = pk["stars"]
        price = pk["price"]
    elif ot == "premium":
        pk = await db.get_premium_package(pid)
        if not pk:
            return await call.answer("❌", show_alert=True)
        info = f"💎 {pk['months']} oy Premium"
        amt_val = pk["months"]
        price = pk["price"]
    else:
        return await call.answer("❌", show_alert=True)

    await state.set_state(OrderFSM.waiting_recipient)
    await state.update_data(order_type=ot, package_info=info, amount_value=amt_val, price=price)

    t = f"🛒 <b>{info}</b>\n💰 <b>{price:,} so'm</b>\n\n{await fmt('ask_username_text')}"
    await call.message.edit_text(t, reply_markup=await kb_ask_username())
    await call.answer()

@user_router.callback_query(F.data == "username:myself")
async def cb_myself(call: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data()
    if not d.get("order_type"):
        await state.clear()
        return await call.answer("❌ Sessiya tugagan", show_alert=True)

    un = f"@{call.from_user.username}" if call.from_user.username else f"<a href='tg://user?id={call.from_user.id}'>{call.from_user.first_name}</a>"
    await process_order_recipient(call.message, call.from_user, un, d, state, bot, is_callback=True)
    await call.answer()

@user_router.message(OrderFSM.waiting_recipient, F.text)
async def recv_recipient(msg: Message, state: FSMContext, bot: Bot):
    r = msg.text.strip()
    if not r.startswith("@"):
        r = "@" + r.lstrip("@")
    if len(r) < 3 or " " in r:
        return await msg.answer("❗️ Noto'g'ri username. Qaytadan kiriting:")

    d = await state.get_data()
    if not d.get("order_type"):
        await state.clear()
        return await msg.answer("❗️ /start bosing.")

    await process_order_recipient(msg, msg.from_user, r, d, state, bot, is_callback=False)

async def process_order_recipient(msg_or_call_msg, user, recipient, d, state, bot, is_callback=False):
    """Orderni yaratadi va to'lov ko'rsatmasini yuboradi"""
    oid = await db.create_order(
        user.id, d["order_type"], d["package_info"],
        d["amount_value"], d["price"], recipient, source="bot"
    )
    await state.update_data(order_id=oid, recipient=recipient)
    await state.set_state(OrderFSM.waiting_payment)

    await try_sticker(bot, msg_or_call_msg.chat.id, "order_sticker")

    card = await db.get_setting("payment_card")
    bank = await db.get_setting("payment_bank")
    holder = await db.get_setting("payment_holder")
    amt = f"{d['price']:,}"

    pt = await fmt("payment_text", card=card, bank=bank, holder=holder, amount=amt)
    pt = pt.replace("{ }", amt).replace("{}", amt)
    t = f"🆔 <code>#{oid}</code>\n📦 {d['package_info']}\n👤 <code>{recipient}</code>\n💰 <b>To'lov: {amt} so'm</b>\n\n{pt}"

    kb = await kb_pay_copy(card, amt)
    if is_callback:
        try:
            await msg_or_call_msg.edit_text(t, reply_markup=kb)
        except Exception:
            await bot.send_message(msg_or_call_msg.chat.id, t, reply_markup=kb)
    else:
        await msg_or_call_msg.answer(t, reply_markup=kb)

@user_router.message(OrderFSM.waiting_payment, F.photo)
async def recv_payment(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    oid = d.get("order_id")
    if not oid:
        await state.clear()
        return await msg.answer("❗️ /start bosing.")

    fid = msg.photo[-1].file_id
    await db.update_order_status(oid, "paid", fid)

    wt = await fmt("waiting_admin_text")
    await msg.answer(f"🆔 <code>#{oid}</code>\n\n{wt}", reply_markup=await kb_back_main())

    u = msg.from_user
    tag = f"@{u.username}" if u.username else f"<a href='tg://user?id={u.id}'>{u.first_name}</a>"
    cap = (
        f"🆕 <b>BUYURTMA</b>\n\n"
        f"🆔 <code>#{oid}</code>\n"
        f"📦 {d['package_info']}\n"
        f"💰 <b>{d['price']:,} so'm</b>\n"
        f"👤 <code>{d['recipient']}</code>\n"
        f"👨‍💻 {tag} (<code>{u.id}</code>)"
    )

    # Asosiy adminga yuborish
    with suppress(Exception):
        await bot.send_photo(
            ADMIN_ID, fid, caption=cap,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"ord:approve:{oid}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"ord:reject:{oid}"),
            ]])
        )

    await state.clear()

@user_router.message(OrderFSM.waiting_payment)
async def recv_payment_wrong(msg: Message):
    await msg.answer("📸 Iltimos, <b>chek rasmini</b> yuboring.")

@user_router.callback_query(F.data == "order:cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await safe_edit(call, await fmt("welcome_text", name=call.from_user.first_name or "do'st"), await kb_main(), bot)
    await call.answer("Bekor qilindi")


# ==========================================================
#   ADMIN HANDLERS
# ==========================================================
async def admin_only(func_msg_or_call):
    """Middleware-ish admin tekshiruv"""
    uid = func_msg_or_call.from_user.id
    return await is_admin(uid)

@admin_router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    if not await is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("🛠 <b>Admin panel</b>", reply_markup=kb_admin_main())

@admin_router.callback_query(F.data == "a:back")
async def cb_admin_back(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    await safe_edit(call, "🛠 <b>Admin panel</b>", kb_admin_main(), bot)
    await call.answer()

@admin_router.callback_query(F.data == "a:stats")
async def cb_stats(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    s = await db.get_stats()
    await call.message.edit_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"📦 Buyurtmalar: <b>{s['orders']}</b>\n"
        f"✅ Bajarilgan: <b>{s['completed']}</b>\n"
        f"⏳ Kutilmoqda: <b>{s['pending']}</b>\n"
        f"⭐ Sotilgan starlar: <b>{s['stars_sold']:,}</b>\n"
        f"💰 Daromad: <b>{s['revenue']:,} so'm</b>",
        reply_markup=kb_back_admin()
    )
    await call.answer()

# ---------- STAR PAKETLAR ----------
@admin_router.callback_query(F.data == "a:stars")
async def cb_admin_stars(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    pkgs = await db.get_star_packages()
    rows = [[InlineKeyboardButton(text=f"⭐ {p['stars']} — {p['price']:,}", callback_data=f"sp:{p['id']}")] for p in pkgs]
    rows += [
        [InlineKeyboardButton(text="➕ Yangi paket", callback_data="sp:add")],
        [InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")],
    ]
    await call.message.edit_text(
        "⭐ <b>Star paketlari</b>\n\nKurs orqali narx hisoblanadi.\nMaxsus narx kerak bo'lsa, paketni tanlab tahrirlang.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("sp:"))
async def cb_sp(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    v = call.data[3:]
    if v == "add":
        await state.set_state(AdminFSM.adding_star_count)
        return await call.message.edit_text("➕ Star sonini kiriting:", reply_markup=kb_cancel("a:stars"))
    pk = await db.get_star_package(int(v))
    if not pk:
        return await call.answer("Topilmadi")
    await call.message.edit_text(
        f"⭐ <b>{pk['stars']} star</b> — <b>{pk['price']:,} so'm</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"spd:{pk['id']}")],
            [InlineKeyboardButton(text="◀️", callback_data="a:stars")],
        ])
    )
    await call.answer()

@admin_router.message(AdminFSM.adding_star_count)
async def msg_add_star(msg: Message, state: FSMContext):
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("❗️ Faqat raqam")
    await db.add_star_package(int(msg.text))
    await state.clear()
    await msg.answer("✅ Qo'shildi", reply_markup=kb_back_admin())

@admin_router.callback_query(F.data.startswith("spd:"))
async def cb_spd(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await db.delete_star_package(int(call.data[4:]))
    await call.answer("✅ O'chirildi", show_alert=True)
    await call.message.edit_text("⭐ <b>Star paketlari</b>", reply_markup=kb_back_admin())

# ---------- STAR KURSI ----------
@admin_router.callback_query(F.data == "a:star_rate")
async def cb_star_rate(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    cur = await db.get_setting("star_rate_uzs")
    await state.set_state(AdminFSM.editing_star_rate)
    await call.message.edit_text(
        f"💱 <b>Star kursi</b>\n\nHozirgi: <b>1 ⭐ = {cur} so'm</b>\n\nYangi kursni kiriting (so'mda):",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_star_rate)
async def msg_star_rate(msg: Message, state: FSMContext):
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("❗️ Faqat raqam")
    await db.set_setting("star_rate_uzs", msg.text)
    await state.clear()
    await msg.answer(f"✅ Yangi kurs: 1 ⭐ = {msg.text} so'm", reply_markup=kb_back_admin())

# ---------- PREMIUM ----------
@admin_router.callback_query(F.data == "a:premium")
async def cb_admin_prem(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    pkgs = await db.get_premium_packages()
    rows = [[InlineKeyboardButton(text=f"💎 {p['months']} oy — {p['price']:,}", callback_data=f"pp:{p['id']}")] for p in pkgs]
    rows.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")])
    await call.message.edit_text("💎 <b>Premium paketlari</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@admin_router.callback_query(F.data.startswith("pp:"))
async def cb_pp(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    pk = await db.get_premium_package(int(call.data[3:]))
    if not pk:
        return await call.answer("Topilmadi")
    await state.set_state(AdminFSM.editing_premium_price)
    await state.update_data(pkg_id=pk["id"])
    await call.message.edit_text(
        f"💎 <b>{pk['months']} oy</b> — hozirgi narx: <b>{pk['price']:,} so'm</b>\n\nYangi narxni kiriting:",
        reply_markup=kb_cancel("a:premium")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_premium_price)
async def msg_prem_price(msg: Message, state: FSMContext):
    if not msg.text or not msg.text.isdigit():
        return await msg.answer("❗️")
    d = await state.get_data()
    await db.update_premium_price(d["pkg_id"], int(msg.text))
    await state.clear()
    await msg.answer("✅", reply_markup=kb_back_admin())

# ---------- TO'LOV KARTA ----------
@admin_router.callback_query(F.data == "a:payment")
async def cb_pay(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    c = await db.get_setting("payment_card")
    b = await db.get_setting("payment_bank")
    h = await db.get_setting("payment_holder")
    await call.message.edit_text(
        f"💳 <b>To'lov karta ma'lumotlari</b>\n\n"
        f"💳 Karta: <code>{c}</code>\n🏦 Bank: {b}\n👤 Egasi: {h}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Karta", callback_data="ep:payment_card")],
            [InlineKeyboardButton(text="🏦 Bank", callback_data="ep:payment_bank")],
            [InlineKeyboardButton(text="👤 Egasi", callback_data="ep:payment_holder")],
            [InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")],
        ])
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("ep:"))
async def cb_ep(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    key = call.data[3:]
    cur = await db.get_setting(key)
    await state.set_state(AdminFSM.editing_payment_info)
    await state.update_data(key=key)
    await call.message.edit_text(
        f"✏️ Hozirgi: <code>{cur}</code>\n\nYangi qiymat:",
        reply_markup=kb_cancel("a:payment")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_payment_info)
async def msg_ep(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    await db.set_setting((await state.get_data())["key"], msg.text.strip())
    await state.clear()
    await msg.answer("✅", reply_markup=kb_back_admin())

# ---------- TO'LOV API (Click/Mirpay) ----------
@admin_router.callback_query(F.data == "a:payment_api")
async def cb_payment_api(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    provider = await db.get_setting("payment_provider") or "qo'lda"
    click_set = "✅" if await db.get_setting("click_secret_key") else "❌"
    mirpay_set = "✅" if await db.get_setting("mirpay_api_key") else "❌"

    text = (
        f"🔌 <b>To'lov API sozlamalari</b>\n\n"
        f"Hozirgi rejim: <b>{provider}</b>\n\n"
        f"{click_set} Click sozlangan\n"
        f"{mirpay_set} Mirpay sozlangan\n\n"
        f"💡 API kalitlarni kiritsangiz — avto to'lov ishga tushadi.\n"
        f"Bo'sh bo'lsa — qo'lda tasdiqlash rejimi."
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔧 Click sozlash", callback_data="api:click")],
        [InlineKeyboardButton(text="🔧 Mirpay sozlash", callback_data="api:mirpay")],
        [
            InlineKeyboardButton(text="✅ Click yoqish", callback_data="api:enable:click"),
            InlineKeyboardButton(text="✅ Mirpay yoqish", callback_data="api:enable:mirpay"),
        ],
        [InlineKeyboardButton(text="🚫 Qo'lda rejimga qaytish", callback_data="api:enable:")],
        [InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")],
    ]))
    await call.answer()

@admin_router.callback_query(F.data.startswith("api:enable:"))
async def cb_api_enable(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    provider = call.data.split(":")[2]
    if provider and not await db.get_setting(f"{provider}_secret_key" if provider == "click" else f"{provider}_api_key"):
        return await call.answer(f"❗️ Avval {provider} kalitlarini sozlang", show_alert=True)
    await db.set_setting("payment_provider", provider)
    mode_name = provider if provider else "qo'lda"
    await call.answer(f"✅ Faol rejim: {mode_name}", show_alert=True)
    await cb_payment_api(call, None)

@admin_router.callback_query(F.data.startswith("api:click") | F.data.startswith("api:mirpay"))
async def cb_api_setup(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    provider = call.data.split(":")[1]
    if provider == "click":
        fields = [
            ("click_merchant_id", "Merchant ID"),
            ("click_service_id", "Service ID"),
            ("click_secret_key", "Secret Key"),
        ]
    else:
        fields = [
            ("mirpay_merchant_id", "Merchant ID"),
            ("mirpay_api_key", "API Key"),
            ("mirpay_secret", "Secret"),
        ]
    rows = []
    for k, label in fields:
        cur = await db.get_setting(k)
        mark = "✅" if cur else "❌"
        rows.append([InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"setapi:{k}")])
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="a:payment_api")])
    await call.message.edit_text(
        f"🔧 <b>{provider.upper()} sozlamalari</b>\n\nHar bir maydonni bosib qiymat kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("setapi:"))
async def cb_setapi(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    key = call.data.split(":")[1]
    await state.set_state(AdminFSM.editing_payment_api_key)
    await state.update_data(key=key)
    await call.message.edit_text(
        f"🔑 <b>{key}</b> qiymatini yuboring:",
        reply_markup=kb_cancel("a:payment_api")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_payment_api_key)
async def msg_setapi(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    d = await state.get_data()
    await db.set_setting(d["key"], msg.text.strip())
    await state.clear()
    # Xavfsizlik — kalitni darrov o'chirib tashlash
    with suppress(Exception):
        await msg.delete()
    await msg.answer(f"✅ Saqlandi: <code>{d['key']}</code>", reply_markup=kb_back_admin())

# ---------- ADMIN USERNAME ----------
@admin_router.callback_query(F.data == "a:username")
async def cb_un(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    cur = await db.get_setting("admin_username")
    await state.set_state(AdminFSM.editing_admin_username)
    await call.message.edit_text(
        f"👨‍💼 Hozirgi: <code>@{cur}</code>\n\nYangi username (@ siz):",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_admin_username)
async def msg_un(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    un = msg.text.strip().lstrip("@")
    if not un or " " in un or len(un) < 3:
        return await msg.answer("❗️ Noto'g'ri")
    await db.set_setting("admin_username", un)
    await state.clear()
    await msg.answer(f"✅ @{un}", reply_markup=kb_back_admin())

# ---------- ADMINLAR (qo'shimcha admin qo'shish) ----------
@admin_router.callback_query(F.data == "a:admins")
async def cb_admins(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("❌ Faqat asosiy admin", show_alert=True)
    await state.set_state(AdminFSM.adding_new_admin)
    await call.message.edit_text(
        "👥 <b>Admin qo'shish</b>\n\nQo'shmoqchi bo'lgan odamning User ID'sini yuboring.\n"
        "Admin huquqini olib tashlash uchun: <code>-USERID</code>",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.adding_new_admin)
async def msg_add_admin(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    txt = msg.text.strip()
    remove = txt.startswith("-")
    if remove:
        txt = txt[1:]
    if not txt.isdigit():
        return await msg.answer("❗️ User ID raqam bo'lishi kerak")
    uid = int(txt)
    user = await db.get_user(uid)
    if not user:
        return await msg.answer("❗️ Bu user botda ro'yxatdan o'tmagan")
    if remove:
        await db.remove_admin(uid)
        await msg.answer(f"✅ Admin huquqi olib tashlandi: <code>{uid}</code>")
    else:
        await db.add_admin(uid)
        await msg.answer(f"✅ Admin qo'shildi: <code>{uid}</code>")
    await state.clear()

# ---------- FOYDALANUVCHI BALANSI ----------
@admin_router.callback_query(F.data == "a:user_balance")
async def cb_user_bal(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AdminFSM.adjust_balance)
    await call.message.edit_text(
        "💰 <b>Balans tahrirlash</b>\n\n"
        "Formatda yuboring:\n<code>USERID SUMMA</code>\n\n"
        "Misol:\n<code>123456789 50000</code> — 50000 qo'shadi\n"
        "<code>123456789 -50000</code> — 50000 ayiradi",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.adjust_balance)
async def msg_adjust_bal(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    parts = msg.text.strip().split()
    if len(parts) != 2:
        return await msg.answer("❗️ Format: USERID SUMMA")
    try:
        uid = int(parts[0])
        amount = int(parts[1])
    except ValueError:
        return await msg.answer("❗️ Raqamlar noto'g'ri")
    user = await db.get_user(uid)
    if not user:
        return await msg.answer("❗️ User topilmadi")
    await db.update_balance(uid, amount, f"Admin tomonidan {amount:+d} so'm", tx_type="manual", payment_method="admin")
    new_bal = (await db.get_user(uid))["balance"]
    await state.clear()
    await msg.answer(
        f"✅ <b>{user['first_name']}</b> (<code>{uid}</code>)\n"
        f"O'zgarish: <b>{amount:+,} so'm</b>\n"
        f"Yangi balans: <b>{new_bal:,} so'm</b>",
        reply_markup=kb_back_admin()
    )

# ---------- REYTING BOSHQARUVI ----------
@admin_router.callback_query(F.data == "a:ratings")
async def cb_ratings(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AdminFSM.set_rating_override)
    await call.message.edit_text(
        "🏆 <b>Reyting boshqaruvi</b>\n\n"
        "Reyting'da 1/2/3 o'rinni qo'lda o'rnatish uchun shu formatda yuboring:\n\n"
        "<code>TYPE POSITION USERID VALUE</code>\n\n"
        "TYPE: <code>spending_alltime</code> | <code>spending_week</code> | <code>spending_month</code> | <code>referral</code>\n"
        "POSITION: <code>1</code> | <code>2</code> | <code>3</code>\n"
        "USERID: user ID raqami\n"
        "VALUE: ko'rsatiladigan qiymat\n\n"
        "Misol:\n<code>spending_alltime 1 123456789 500000</code>\n\n"
        "🗑 O'chirish: <code>del TYPE POSITION</code>\n"
        "Misol: <code>del spending_alltime 1</code>",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.set_rating_override)
async def msg_rating_ov(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    parts = msg.text.strip().split()

    if len(parts) == 3 and parts[0] == "del":
        rtype = parts[1]
        pos = int(parts[2])
        await db.remove_rating_override(rtype, pos)
        await state.clear()
        return await msg.answer(f"✅ {rtype} #{pos} o'chirildi", reply_markup=kb_back_admin())

    if len(parts) != 4:
        return await msg.answer("❗️ Format noto'g'ri. Yuqorida ko'rsatilgan misolga qarang.")
    try:
        rtype, pos, uid, val = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return await msg.answer("❗️ Raqamlar noto'g'ri")
    if rtype not in ("spending_alltime", "spending_week", "spending_month", "referral"):
        return await msg.answer("❗️ TYPE noto'g'ri")
    if pos not in (1, 2, 3):
        return await msg.answer("❗️ POSITION 1, 2 yoki 3 bo'lishi kerak")
    user = await db.get_user(uid)
    if not user:
        return await msg.answer("❗️ User topilmadi")
    await db.set_rating_override(rtype, pos, uid, val)
    await state.clear()
    await msg.answer(
        f"✅ Reyting o'zgartirildi\n\n"
        f"Tur: <b>{rtype}</b>\n"
        f"O'rin: <b>#{pos}</b>\n"
        f"User: <b>{user['first_name']}</b>\n"
        f"Qiymat: <b>{val:,}</b>",
        reply_markup=kb_back_admin()
    )

# ---------- MATNLAR ----------
@admin_router.callback_query(F.data == "a:texts")
async def cb_texts(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    rows = [[InlineKeyboardButton(text=l, callback_data=f"et:{k}")] for k, l in EDITABLE_TEXTS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")])
    await call.message.edit_text(
        "📝 <b>Matnlar</b>\n\n💡 O'zgaruvchilar: <code>{name}</code> <code>{admin}</code> <code>{card}</code> <code>{bank}</code> <code>{holder}</code> <code>{amount}</code> <code>{webapp_url}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await call.answer()

@admin_router.callback_query(F.data.startswith("et:"))
async def cb_et(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    key = call.data[3:]
    cur = await db.get_setting(key)
    await state.set_state(AdminFSM.editing_text)
    await state.update_data(key=key)
    await call.message.edit_text(
        f"📝 <b>{EDITABLE_TEXTS.get(key)}</b>\n\nHozirgi:\n<code>{cur}</code>\n\nYangi matn yuboring:",
        reply_markup=kb_cancel("a:texts")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_text)
async def msg_et(msg: Message, state: FSMContext):
    new = msg.html_text if (msg.text or msg.caption) else None
    if not new:
        return await msg.answer("❗️ Matn yuboring")
    await db.set_setting((await state.get_data())["key"], new)
    await state.clear()
    await msg.answer("✅ Saqlandi", reply_markup=kb_back_admin())

# ---------- TUGMA NOMLARI ----------
@admin_router.callback_query(F.data == "a:buttons")
async def cb_btns(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    rows = [[InlineKeyboardButton(text=l, callback_data=f"eb:{k}")] for k, l in BTN_KEYS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")])
    await call.message.edit_text("🔘 <b>Tugma nomlari</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@admin_router.callback_query(F.data.startswith("eb:"))
async def cb_eb(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    key = call.data[3:]
    cur = await db.get_setting(key)
    await state.set_state(AdminFSM.editing_button)
    await state.update_data(key=key)
    await call.message.edit_text(
        f"🔘 Hozirgi: <code>{cur}</code>\n\nYangi nom:",
        reply_markup=kb_cancel("a:buttons")
    )
    await call.answer()

@admin_router.message(AdminFSM.editing_button)
async def msg_eb(msg: Message, state: FSMContext):
    if not msg.text or len(msg.text) > 60:
        return await msg.answer("❗️ 60 belgidan kam bo'lsin")
    await db.set_setting((await state.get_data())["key"], msg.text.strip())
    await state.clear()
    await msg.answer("✅", reply_markup=kb_back_admin())

# ---------- STIKERLAR ----------
@admin_router.callback_query(F.data == "a:stickers")
async def cb_stk(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    lines = ["🎨 <b>Stikerlar</b>\n"]
    for k, l in STICKER_SLOTS.items():
        lines.append(f"• {l}: {'✅' if await db.get_setting(k) else '❌'}")
    rows = [[InlineKeyboardButton(text=l, callback_data=f"ss:{k}")] for k, l in STICKER_SLOTS.items()]
    rows.append([InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@admin_router.callback_query(F.data.startswith("ss:"))
async def cb_ss(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    key = call.data[3:]
    await state.set_state(AdminFSM.setting_sticker)
    await state.update_data(key=key)
    await call.message.edit_text("🎨 Stiker yuboring\n🗑 O'chirish: <code>-</code>", reply_markup=kb_cancel("a:stickers"))
    await call.answer()

@admin_router.message(AdminFSM.setting_sticker, F.sticker)
async def msg_ss(msg: Message, state: FSMContext):
    await db.set_setting((await state.get_data())["key"], msg.sticker.file_id)
    await state.clear()
    await msg.answer("✅", reply_markup=kb_back_admin())

@admin_router.message(AdminFSM.setting_sticker, F.text == "-")
async def msg_ss_clr(msg: Message, state: FSMContext):
    await db.set_setting((await state.get_data())["key"], "")
    await state.clear()
    await msg.answer("🗑", reply_markup=kb_back_admin())

@admin_router.message(AdminFSM.setting_sticker)
async def msg_ss_w(msg: Message):
    await msg.answer("❗️ Stiker yoki <code>-</code> yuboring")

# ---------- BOT VIDEO ----------
@admin_router.callback_query(F.data == "a:about_video")
async def cb_av(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AdminFSM.setting_about_video)
    st = "✅" if await db.get_setting("about_video") else "❌"
    await call.message.edit_text(
        f"🎥 <b>Bot haqida video</b> ({st})\n\nVideo yuboring.\n🗑 <code>-</code>",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.setting_about_video, F.video)
async def msg_av(msg: Message, state: FSMContext):
    await db.set_setting("about_video", msg.video.file_id)
    await state.clear()
    await msg.answer("✅", reply_markup=kb_back_admin())

@admin_router.message(AdminFSM.setting_about_video, F.text == "-")
async def msg_av_clr(msg: Message, state: FSMContext):
    await db.set_setting("about_video", "")
    await state.clear()
    await msg.answer("🗑", reply_markup=kb_back_admin())

# ---------- TOLOVLAR KANALI ----------
@admin_router.callback_query(F.data == "a:proof_ch")
async def cb_pc(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    cur = await db.get_setting("proof_channel") or "yo'q"
    await state.set_state(AdminFSM.setting_proof_channel)
    await call.message.edit_text(
        f"📢 <b>Tolovlar kanali</b>\n\nHozirgi: <code>{cur}</code>\n\n"
        f"Kanal username (<code>@channel</code>).\n⚠️ Bot kanalda admin bo'lishi shart!\n🗑 <code>-</code>",
        reply_markup=kb_cancel("a:back")
    )
    await call.answer()

@admin_router.message(AdminFSM.setting_proof_channel)
async def msg_pc(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    if msg.text.strip() == "-":
        await db.set_setting("proof_channel", "")
        await state.clear()
        return await msg.answer("🗑", reply_markup=kb_back_admin())
    ch = msg.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    await db.set_setting("proof_channel", ch)
    await state.clear()
    await msg.answer(f"✅ {ch}\n\n⚠️ Botni kanalga ADMIN qiling!", reply_markup=kb_back_admin())

# ---------- MAJBURIY OBUNA ----------
@admin_router.callback_query(F.data == "a:req_ch")
async def cb_rc(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    chs = await db.get_required_channels()
    t = "📌 <b>Majburiy obuna kanallari</b>\n\n"
    t += "\n".join(f"• {ti} ({ci})" for _, ci, ti in chs) if chs else "Kanallar yo'q."
    t += "\n\n⚠️ Bot har kanalda admin bo'lishi shart!"

    rows = [[InlineKeyboardButton(text=f"🗑 {ti}", callback_data=f"del_ch:{cid}")] for cid, _, ti in chs]
    rows += [
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch")],
        [InlineKeyboardButton(text="◀️ Admin panel", callback_data="a:back")],
    ]
    await call.message.edit_text(t, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@admin_router.callback_query(F.data.startswith("del_ch:"))
async def cb_dc(call: CallbackQuery):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await db.remove_required_channel(int(call.data.split(":")[1]))
    await call.answer("✅", show_alert=True)
    await cb_rc(call, None)

@admin_router.callback_query(F.data == "add_ch")
async def cb_ac(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AdminFSM.adding_channel_id)
    await call.message.edit_text("📌 Kanal username (<code>@channel</code>):", reply_markup=kb_cancel("a:req_ch"))
    await call.answer()

@admin_router.message(AdminFSM.adding_channel_id)
async def msg_aci(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    ch = msg.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    await state.update_data(ch_id=ch)
    await state.set_state(AdminFSM.adding_channel_title)
    await msg.answer(f"<code>{ch}</code>\n\nKanal <b>nomini</b> yuboring:")

@admin_router.message(AdminFSM.adding_channel_title)
async def msg_act(msg: Message, state: FSMContext):
    if not msg.text:
        return await msg.answer("❗️")
    d = await state.get_data()
    await db.add_required_channel(d["ch_id"], msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ {msg.text.strip()} qo'shildi", reply_markup=kb_back_admin())

# ---------- BROADCAST ----------
@admin_router.callback_query(F.data == "a:broadcast")
async def cb_bc(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AdminFSM.broadcasting)
    await call.message.edit_text("📢 Hammaga yuboriladigan xabarni yuboring:", reply_markup=kb_cancel("a:back"))
    await call.answer()

@admin_router.message(AdminFSM.broadcasting)
async def msg_bc(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    uids = await db.get_all_user_ids()
    total = len(uids)
    sent = failed = 0
    st = await msg.answer(f"📤 0/{total}")
    for i, uid in enumerate(uids, 1):
        try:
            await bot.copy_message(uid, msg.chat.id, msg.message_id)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            with suppress(Exception):
                await st.edit_text(f"📤 {i}/{total}")
            await asyncio.sleep(1)
    await st.edit_text(
        f"✅ Yuborildi: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>\n👥 Jami: <b>{total}</b>",
        reply_markup=kb_back_admin()
    )

# ---------- BUYURTMA TASDIQ/RAD ----------
@admin_router.callback_query(F.data.startswith("ord:"))
async def cb_ord(call: CallbackQuery, bot: Bot):
    if not await is_admin(call.from_user.id):
        return await call.answer()
    _, act, oid = call.data.split(":")
    oid = int(oid)
    o = await db.get_order(oid)
    if not o:
        return await call.answer("Topilmadi", show_alert=True)

    uid = o["user_id"]
    info = o["package_info"]
    price = o["price"]

    if act == "approve":
        await db.update_order_status(oid, "completed")
        await try_sticker(bot, uid, "success_sticker")
        with suppress(Exception):
            await bot.send_message(uid, f"🆔 <code>#{oid}</code>\n📦 {info}\n\n{await fmt('order_completed_text')}")
        with suppress(TelegramBadRequest):
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ <b>TASDIQLANDI</b>")

        pc = await db.get_setting("proof_channel")
        if pc:
            now = datetime.now().strftime("%d.%m.%Y %H:%M")
            with suppress(Exception):
                await bot.send_message(
                    pc,
                    f"✅ <b>Yangi xarid!</b>\n\n📦 {info}\n💰 {price:,} so'm\n👤 {o['recipient'] or '—'}\n🕐 {now}"
                )
        await call.answer("✅", show_alert=True)

    elif act == "reject":
        await db.update_order_status(oid, "rejected")
        with suppress(Exception):
            await bot.send_message(uid, f"🆔 <code>#{oid}</code>\n📦 {info}\n\n{await fmt('order_rejected_text')}")
        with suppress(TelegramBadRequest):
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ <b>RAD ETILDI</b>")
        await call.answer("❌", show_alert=True)


# ==========================================================
#   ENTRY POINT (faqat alohida ishlatish uchun)
# ==========================================================
async def setup_bot():
    """Botni sozlaydi va polling'ni qaytaradi"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    await db.init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)
    await bot.delete_webhook(drop_pending_updates=True)
    return bot, dp


async def main():
    bot, dp = await setup_bot()
    logging.info("✅ Tezkor Star Bot ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
