#!/usr/bin/env python3
"""LumoNews — Telegram edition (stock / values / services)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core import (
    fetch_stock,
    fetch_values_structured,
    format_stock_message,
    format_values_category,
    stock_content_signature,
    values_change_significant,
    values_content_signature,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("LumoNewsTG")

# Token provided by owner — keep private on the host.
TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "9039398570:AAHOzrY42xDjl2_54CjgvwToZKLt6Aq7oiM",
).strip()

# Comma-separated Telegram numeric user IDs. Empty = first /setadmin claim works once.
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "8990071284").strip()
ADMIN_IDS: set[int] = set()
for part in ADMIN_IDS_RAW.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.add(int(part))

DB_PATH = Path(os.getenv("TELEGRAM_DB_PATH", "telegram_data.json"))
POLL_SECONDS = max(8, int(os.getenv("STOCK_POLL_SECONDS", "15")))
VALUES_POLL_SECONDS = max(120, int(os.getenv("VALUES_POLL_SECONDS", "300")))
VALUES_BROADCAST_COOLDOWN = max(600, int(os.getenv("VALUES_BROADCAST_COOLDOWN_SECONDS", "1800")))

DEFAULT_SERVICE_PRICES: dict[str, int] = {
    "level": 10000,
    "items": 20000,
    "raid": 15000,
    "mastery": 15000,
    "fragments": 15000,
    "boss": 12000,
    "race_v4": 80000,
    "awakening": 20000,
    "fruit_farm": 18000,
    "materials": 15000,
    "quests": 12000,
    "sea_events": 25000,
    "mirage": 35000,
    "leviathan": 50000,
    "terror_shark": 30000,
    "soul_guitar": 40000,
    "cdk": 40000,
    "hallow_scythe": 30000,
    "tushita": 30000,
    "yama": 30000,
    "halloween_candy": 2350,
    "account_buy": 0,
    "account_sell": 0,
    "middleman": 0,
}

SERVICE_TITLES: dict[str, str] = {
    "level": "لول‌آپ (هر ۱۰۰ لول)",
    "items": "گرفتن آیتم",
    "raid": "رید",
    "mastery": "مستری",
    "fragments": "فرگمنت",
    "boss": "فارم باس",
    "race_v4": "ریس V4",
    "awakening": "فول بیداری میوه",
    "fruit_farm": "فارم میوه",
    "materials": "جمع‌آوری متریال",
    "quests": "مأموریت",
    "sea_events": "ایونت دریا",
    "mirage": "میراژ",
    "leviathan": "لویاتان",
    "terror_shark": "ترور شارک",
    "soul_guitar": "سول گیتار",
    "cdk": "CDK",
    "hallow_scythe": "هالو سایث",
    "tushita": "توشیتا",
    "yama": "یاما",
    "halloween_candy": "کندی هالوین (هر ۱۰۰ تا)",
    "account_buy": "خرید اکانت",
    "account_sell": "فروش اکانت",
    "middleman": "واسطه‌گری رایگان",
}

DB: dict[str, Any] = {
    "users": {},
    "chats": {},
    "meta": {},
    "settings": {},
    "subscriptions": {},
    "services": {},
    "service_state": {},
    "support_state": {},
    "service_requests": {},
}

CACHE: dict[str, Any] = {
    "stock": None,
    "stock_at": 0.0,
    "values_struct": None,
    "values_at": 0.0,
}

MONITOR_STARTED = False


def load_db() -> None:
    global DB, ADMIN_IDS
    if DB_PATH.is_file():
        try:
            data = json.loads(DB_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    DB[k] = v
        except Exception as exc:
            log.warning("DB load failed: %s", exc)
    # Persist admin list from DB if env empty
    stored = DB.get("settings", {}).get("admin_ids") or []
    if not ADMIN_IDS and isinstance(stored, list):
        for x in stored:
            try:
                ADMIN_IDS.add(int(x))
            except (TypeError, ValueError):
                pass


def save_db() -> None:
    try:
        DB.setdefault("settings", {})["admin_ids"] = sorted(ADMIN_IDS)
        DB_PATH.write_text(json.dumps(DB, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.warning("DB save failed: %s", exc)


def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


def service_price_of(key: str) -> int:
    saved = (DB.get("services") or {}).get(key) or {}
    if isinstance(saved, dict) and saved.get("price") is not None:
        try:
            return int(saved["price"])
        except (TypeError, ValueError):
            pass
    return int(DEFAULT_SERVICE_PRICES.get(key) or 0)


def format_service_price(key: str) -> str:
    if key == "middleman":
        return "رایگان"
    price = service_price_of(key)
    if price == 0 and key in ("account_buy", "account_sell"):
        return "با هماهنگی ادمین"
    if price == 0:
        return "رایگان"
    return f"{price:,} تومان"


def halloween_candy_price_table() -> str:
    unit = service_price_of("halloween_candy") or 2350
    lines = [
        "🎃 جدول قیمت کندی هالوین",
        f"مبنای قیمت: هر ۱۰۰ کندی = {unit:,} تومان",
        "━━━━━━━━━━━━━━",
    ]
    for amount in range(100, 10001, 100):
        total = (amount // 100) * unit
        lines.append(f"{amount:,} کندی = {total:,} تومان")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("تعداد را در یک پیام بفرست (مثلاً: ۵۰۰۰ کندی).")
    return "\n".join(lines)


def main_keyboard(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton("📦 استاک الان"), KeyboardButton("💎 ولیو میوه‌ها")],
        [KeyboardButton("🛍 خدمات بلاکس فروت"), KeyboardButton("📖 راهنما")],
        [KeyboardButton("🆔 آیدی من")],
    ]
    if is_admin(uid):
        rows.append([KeyboardButton("🛠 مدیریت")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def values_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💎 دائمی"), KeyboardButton("🍎 میوه")],
            [KeyboardButton("⌛ لیمیتد"), KeyboardButton("🎟️ گیم‌پس")],
            [KeyboardButton("🏠 منوی اصلی")],
        ],
        resize_keyboard=True,
    )


def services_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🚀 لول‌آپ"), KeyboardButton("🎒 گرفتن آیتم")],
            [KeyboardButton("⚔️ رید"), KeyboardButton("📈 مستری")],
            [KeyboardButton("💎 فرگمنت"), KeyboardButton("👹 فارم باس")],
            [KeyboardButton("🧬 ریس V4"), KeyboardButton("🔥 فول بیداری میوه")],
            [KeyboardButton("🍈 فارم میوه"), KeyboardButton("🧱 متریال")],
            [KeyboardButton("📜 مأموریت"), KeyboardButton("🌊 ایونت دریا")],
            [KeyboardButton("🏝️ میراژ"), KeyboardButton("🐋 لویاتان")],
            [KeyboardButton("🦈 ترور شارک"), KeyboardButton("🎸 سول گیتار")],
            [KeyboardButton("⚔️ CDK"), KeyboardButton("🌙 هالو سایث")],
            [KeyboardButton("🗡️ توشیتا"), KeyboardButton("🗡️ یاما")],
            [KeyboardButton("🎃 کندی هالوین")],
            [KeyboardButton("🛒 خرید اکانت"), KeyboardButton("💰 فروش اکانت")],
            [KeyboardButton("🤝 واسطه رایگان"), KeyboardButton("🏠 منوی اصلی")],
        ],
        resize_keyboard=True,
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 آمار"), KeyboardButton("📡 وضعیت")],
            [KeyboardButton("🔄 رفرش استاک"), KeyboardButton("🔄 رفرش ولیو")],
            [KeyboardButton("📣 پیام سراسری")],
            [KeyboardButton("🏠 منوی اصلی")],
        ],
        resize_keyboard=True,
    )


SERVICE_BUTTONS = {
    "🚀 لول‌آپ": ("level", "لول‌آپ اکانت"),
    "🎒 گرفتن آیتم": ("items", "گرفتن آیتم"),
    "⚔️ رید": ("raid", "رید"),
    "📈 مستری": ("mastery", "مستری"),
    "💎 فرگمنت": ("fragments", "فرگمنت"),
    "👹 فارم باس": ("boss", "فارم باس"),
    "🧬 ریس V4": ("race_v4", "ریس V4"),
    "🔥 فول بیداری میوه": ("awakening", "فول بیداری میوه"),
    "🍈 فارم میوه": ("fruit_farm", "فارم میوه"),
    "🧱 متریال": ("materials", "جمع‌آوری متریال"),
    "📜 مأموریت": ("quests", "مأموریت"),
    "🌊 ایونت دریا": ("sea_events", "ایونت دریا"),
    "🏝️ میراژ": ("mirage", "میراژ"),
    "🐋 لویاتان": ("leviathan", "لویاتان"),
    "🦈 ترور شارک": ("terror_shark", "ترور شارک"),
    "🎸 سول گیتار": ("soul_guitar", "سول گیتار"),
    "⚔️ CDK": ("cdk", "CDK"),
    "🌙 هالو سایث": ("hallow_scythe", "هالو سایث"),
    "🗡️ توشیتا": ("tushita", "توشیتا"),
    "🗡️ یاما": ("yama", "یاما"),
    "🎃 کندی هالوین": ("halloween_candy", "کندی هالوین"),
    "🛒 خرید اکانت": ("account_buy", "خرید اکانت"),
    "💰 فروش اکانت": ("account_sell", "فروش اکانت"),
    "🤝 واسطه رایگان": ("middleman", "واسطه‌گری رایگان"),
}


async def safe_reply(update: Update, text: str, **kwargs) -> None:
    if not update.effective_message:
        return
    body = (text or "—").strip() or "—"
    # Telegram hard limit ~4096
    while body:
        chunk = body[:4000]
        body = body[4000:]
        await update.effective_message.reply_text(chunk, **kwargs)
        kwargs = {}  # keyboard only on first chunk


def remember_user(update: Update) -> tuple[int, int]:
    user = update.effective_user
    chat = update.effective_chat
    uid = int(user.id) if user else 0
    cid = int(chat.id) if chat else uid
    now = int(time.time())
    rec = DB.setdefault("users", {}).setdefault(str(uid), {})
    rec["chat_id"] = cid
    rec["started"] = True
    rec["last_seen"] = now
    rec.setdefault("first_seen", now)
    if user:
        if user.username:
            rec["username"] = user.username
        name = " ".join(x for x in [user.first_name, user.last_name] if x).strip()
        if name:
            rec["name"] = name
    DB.setdefault("chats", {}).setdefault(str(cid), {"first_seen": now})["last_seen"] = now
    # Auto-subscribe groups/supergroups/channels where bot can post
    if chat and chat.type in ("group", "supergroup", "channel"):
        subs = DB.setdefault("subscriptions", {})
        key = str(cid)
        if key not in subs:
            subs[key] = {
                "owner_id": str(uid),
                "stock": True,
                "values": True,
                "type": chat.type,
                "title": getattr(chat, "title", "") or "",
                "added_at": now,
            }
        else:
            subs[key]["last_seen"] = now
    save_db()
    return uid, cid


async def get_stock_cached(force: bool = False) -> dict[str, Any]:
    if not force and CACHE.get("stock") and time.monotonic() - CACHE["stock_at"] < 25:
        return CACHE["stock"]
    data = await asyncio.to_thread(fetch_stock)
    CACHE["stock"] = data
    CACHE["stock_at"] = time.monotonic()
    DB.setdefault("meta", {})["last_stock_ok_at"] = int(time.time())
    DB["meta"]["stock_snapshot"] = data
    save_db()
    return data


async def get_values_struct(force: bool = False) -> dict[str, Any]:
    if not force and CACHE.get("values_struct") and time.monotonic() - CACHE["values_at"] < 240:
        return CACHE["values_struct"]
    structured = await asyncio.to_thread(fetch_values_structured)
    CACHE["values_struct"] = structured
    CACHE["values_at"] = time.monotonic()
    DB.setdefault("meta", {})["last_values_ok_at"] = int(time.time())
    DB["meta"]["values_snapshot"] = structured
    save_db()
    return structured


async def send_chunks_chat(bot, chat_id: int, chunks: list[str]) -> bool:
    ok = True
    for chunk in chunks:
        try:
            await bot.send_message(chat_id, chunk[:4000])
        except Exception as exc:
            log.warning("send %s failed: %s", chat_id, exc)
            ok = False
    return ok


def collect_broadcast_targets() -> list[int]:
    targets: list[int] = []
    seen: set[int] = set()

    def add(raw: Any) -> None:
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            return
        if tid in seen:
            return
        seen.add(tid)
        targets.append(tid)

    for key, sub in (DB.get("subscriptions") or {}).items():
        if isinstance(sub, dict):
            add(key)
    for key, info in (DB.get("users") or {}).items():
        if not isinstance(info, dict):
            continue
        if info.get("started") is False:
            continue
        add(info.get("chat_id") or key)
    return targets


async def notify_admins(bot, text: str) -> bool:
    if not ADMIN_IDS:
        log.warning("No ADMIN_IDS configured; cannot notify")
        return False
    any_ok = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text[:4000])
            any_ok = True
        except Exception as exc:
            log.warning("Admin notify %s failed: %s", admin_id, exc)
    return any_ok


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    name = update.effective_user.first_name if update.effective_user else "کاربر"
    count = sum(1 for u in (DB.get("users") or {}).values() if isinstance(u, dict) and u.get("started"))
    text = (
        f"سلام {name} عزیز! 🎉\n\n"
        f"👥 کاربران: {count:,} نفر\n\n"
        "به ربات 🤖 LumoNews خوش اومدی.\n\n"
        "📦 استاک الان — استاک فعلی\n"
        "💎 ولیو میوه‌ها — ارزش آیتم‌ها\n"
        "🛍 خدمات بلاکس فروت — ثبت درخواست\n\n"
        "👑 سازنده: @Orginal_Lumo\n"
        "🤖 LumoNews"
    )
    await safe_reply(update, text, reply_markup=main_keyboard(uid))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    text = (
        "📖 راهنمای LumoNews\n\n"
        "/start — منوی اصلی\n"
        "/stock — استاک فعلی\n"
        "/values — منوی ولیو\n"
        "/fruits /permanent /limiteds /gamepasses\n"
        "/id — شناسه تلگرام شما\n"
        "/services — خدمات بلاکس فروت\n"
    )
    if is_admin(uid):
        text += (
            "\nادمین:\n"
            "/broadcast متن — پیام سراسری\n"
            "/servicereply شماره متن — پاسخ به درخواست خدمات\n"
            "/serviceclose شماره — بستن درخواست\n"
            "/setadmin — ثبت خودت به‌عنوان ادمین (اگر لیست خالی باشد)\n"
        )
    await safe_reply(update, text, reply_markup=main_keyboard(uid))


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, cid = remember_user(update)
    uname = update.effective_user.username if update.effective_user else ""
    extra = f"\nیوزرنیم: @{uname}" if uname else ""
    await safe_reply(
        update,
        f"🆔 شناسه‌ها\n\nشناسه کاربر: `{uid}`\nشناسه چت: `{cid}`{extra}",
    )


async def cmd_setadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    if ADMIN_IDS and uid not in ADMIN_IDS:
        await safe_reply(update, "⛔️ لیست ادمین از قبل تنظیم شده است.")
        return
    ADMIN_IDS.add(uid)
    save_db()
    await safe_reply(update, f"✅ شما ادمین شدید.\nID: {uid}", reply_markup=main_keyboard(uid))


async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    remember_user(update)
    try:
        data = await get_stock_cached()
        for chunk in format_stock_message(data):
            await safe_reply(update, chunk.replace("@LumoNews_Bot", "LumoNews TG").replace("@LumoNews", "LumoNews"))
    except Exception as exc:
        await safe_reply(update, f"⚠️ استاک در دسترس نیست.\n{exc}")


async def send_values_cat(update: Update, key: str, title: str) -> None:
    remember_user(update)
    try:
        s = await get_values_struct()
        if s.get("_stale"):
            title = "⚠️ آخرین ولیو ذخیره‌شده\n" + title
        uid = str(update.effective_user.id) if update.effective_user else ""
        chunks = format_values_category(
            s.get(key) or {},
            title=title,
            user_id=uid,
            footer="🤖 LumoNews",
        )
        for chunk in chunks:
            await safe_reply(update, chunk)
    except Exception as exc:
        await safe_reply(update, f"⚠️ {exc}")


async def cmd_values(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    await safe_reply(update, "💎 بخش ولیو\nیک دسته را انتخاب کن:", reply_markup=values_keyboard())


async def cmd_fruits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_values_cat(update, "fruits", "🍎 میوه\n🤖 LumoNews")


async def cmd_permanent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_values_cat(update, "permanent", "💎 دائمی\n🤖 LumoNews")


async def cmd_limiteds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_values_cat(update, "limiteds", "⌛ لیمیتد\n🤖 LumoNews")


async def cmd_gamepasses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_values_cat(update, "gamepasses", "🎟️ گیم‌پس\n🤖 LumoNews")


async def cmd_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    lines = ["🛍 خدمات بلاکس فروت | LumoNews", "━━━━━━━━━━━━━━"]
    for key, title in SERVICE_TITLES.items():
        lines.append(f"• {title} — {format_service_price(key)}")
    lines.append("\n👇 از منو یک خدمات را انتخاب کن.")
    await safe_reply(update, "\n".join(lines), reply_markup=services_keyboard())


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    if not is_admin(uid):
        await safe_reply(update, "⛔️ فقط ادمین.")
        return
    body = " ".join(context.args).strip() if context.args else ""
    if not body:
        DB.setdefault("support_state", {})[str(uid)] = {
            "mode": "awaiting_global_broadcast",
            "created_at": int(time.time()),
        }
        save_db()
        await safe_reply(update, "📣 متن پیام سراسری را بفرست.\nبرای لغو: لغو")
        return
    await do_broadcast(update, context, body)


async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, body: str) -> None:
    payload = f"📣 پیام سراسری ادمین\n━━━━━━━━━━━━━━━━━━\n{body}"
    targets = collect_broadcast_targets()
    if not targets:
        await safe_reply(update, "❌ مقصدی پیدا نشد.")
        return
    await safe_reply(update, f"⏳ ارسال به {len(targets)} مقصد…")
    sent = failed = 0
    for i, tid in enumerate(targets):
        try:
            await context.bot.send_message(tid, payload[:4000])
            sent += 1
        except Exception:
            failed += 1
        if i % 20 == 19:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(0.05)
    await safe_reply(update, f"✅ تمام شد.\nموفق: {sent}\nناموفق: {failed}")


async def cmd_servicereply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    if not is_admin(uid):
        await safe_reply(update, "⛔️ فقط ادمین.")
        return
    if len(context.args) < 2:
        await safe_reply(update, "فرمت:\n/servicereply شماره متن پاسخ")
        return
    tid = context.args[0]
    answer = " ".join(context.args[1:])
    req = (DB.get("service_requests") or {}).get(tid)
    if not isinstance(req, dict):
        await safe_reply(update, "درخواست خدمات پیدا نشد.")
        return
    target = int(req.get("chat_id") or req.get("user_id") or 0)
    try:
        await context.bot.send_message(
            target,
            f"💬 پاسخ ادمین به درخواست خدمات #{tid}\n"
            f"خدمات: {req.get('service', '—')}\n\n{answer}",
        )
        req["status"] = "answered"
        req["answer"] = answer
        save_db()
        await safe_reply(update, f"✅ پاسخ #{tid} ارسال شد.")
    except Exception as exc:
        await safe_reply(update, f"❌ ارسال ناموفق: {exc}")


async def cmd_serviceclose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid, _ = remember_user(update)
    if not is_admin(uid):
        await safe_reply(update, "⛔️ فقط ادمین.")
        return
    if not context.args:
        await safe_reply(update, "فرمت:\n/serviceclose شماره [دلیل]")
        return
    tid = context.args[0]
    reason = " ".join(context.args[1:]) or "درخواست بسته شد."
    req = (DB.get("service_requests") or {}).get(tid)
    if not isinstance(req, dict):
        await safe_reply(update, "درخواست خدمات پیدا نشد.")
        return
    req["status"] = "closed"
    save_db()
    try:
        await context.bot.send_message(
            int(req.get("chat_id") or req.get("user_id")),
            f"🔒 درخواست خدمات #{tid} بسته شد.\n{reason}",
        )
    except Exception:
        pass
    await safe_reply(update, f"درخواست #{tid} بسته شد.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.message:
        return
    text = (update.message.text or "").strip()
    if not text:
        return
    uid, cid = remember_user(update)
    uid_s = str(uid)

    # Broadcast composer
    st = (DB.get("support_state") or {}).get(uid_s) or {}
    if st.get("mode") == "awaiting_global_broadcast" and is_admin(uid):
        if text in ("لغو", "انصراف"):
            DB["support_state"].pop(uid_s, None)
            save_db()
            await safe_reply(update, "❎ لغو شد.", reply_markup=admin_keyboard())
            return
        DB["support_state"].pop(uid_s, None)
        save_db()
        await do_broadcast(update, context, text)
        return

    # Service details
    service_states = DB.setdefault("service_state", {})
    if uid_s in service_states and not text.startswith("/"):
        if text in ("لغو", "انصراف"):
            service_states.pop(uid_s, None)
            save_db()
            await safe_reply(update, "درخواست خدمات لغو شد.", reply_markup=main_keyboard(uid))
            return
        state = service_states.pop(uid_s)
        save_db()
        tid = f"{int(time.time())}{str(uid)[-4:]}"
        uname = (update.effective_user.username if update.effective_user else "") or ""
        name = (update.effective_user.full_name if update.effective_user else "") or "کاربر"
        service_key = str(state.get("service") or "")
        req = {
            "id": tid,
            "user_id": uid,
            "chat_id": cid,
            "username": uname,
            "name": name,
            "service_key": service_key,
            "service": state.get("title", "خدمات"),
            "details": text[:2500],
            "price_text": format_service_price(service_key),
            "status": "pending",
            "created_at": int(time.time()),
        }
        DB.setdefault("service_requests", {})[tid] = req
        save_db()
        if uname:
            user_line = f"کاربر: {name}\nیوزرنیم: @{uname}\nپیوی: https://t.me/{uname}"
        else:
            user_line = f"کاربر: {name}\nشناسه: {uid}\n(یوزرنیم ندارد — با /servicereply جواب بده)"
        admin_msg = (
            f"🛍 درخواست خدمات جدید #{tid}\n"
            f"خدمات: {req['service']}\n"
            f"قیمت فهرست: {req['price_text']}\n"
            f"{user_line}\n\n"
            f"جزئیات:\n{text[:2200]}\n\n"
            f"پاسخ:\n/servicereply {tid} متن\n"
            f"بستن:\n/serviceclose {tid}"
        )
        sent = await notify_admins(context.bot, admin_msg)
        if sent:
            await safe_reply(
                update,
                f"✅ درخواستت ثبت شد و برای ادمین ارسال شد.\nشماره پیگیری: #{tid}",
                reply_markup=main_keyboard(uid),
            )
        else:
            await safe_reply(
                update,
                f"⚠️ درخواست ذخیره شد (#{tid}) ولی ارسال به ادمین ناموفق بود.\n"
                f"اگر ادمین هنوز /setadmin نزده، اول باید ادمین ثبت شود.",
                reply_markup=main_keyboard(uid),
            )
        return

    # Menus
    if text in ("🏠 منوی اصلی", "منوی اصلی"):
        await safe_reply(update, "منوی اصلی LumoNews:", reply_markup=main_keyboard(uid))
        return
    if text in ("📖 راهنما", "راهنما"):
        await cmd_help(update, context)
        return
    if text in ("🆔 آیدی من",):
        await cmd_id(update, context)
        return
    if text in ("📦 استاک الان", "استاک"):
        await cmd_stock(update, context)
        return
    if text in ("💎 ولیو میوه‌ها", "ولیو", "ولیوها"):
        await cmd_values(update, context)
        return
    if text in ("💎 دائمی",):
        await cmd_permanent(update, context)
        return
    if text in ("🍎 میوه",):
        await cmd_fruits(update, context)
        return
    if text in ("⌛ لیمیتد",):
        await cmd_limiteds(update, context)
        return
    if text in ("🎟️ گیم‌پس", "گیم‌پس"):
        await cmd_gamepasses(update, context)
        return
    if text in ("🛍 خدمات بلاکس فروت", "خدمات"):
        await cmd_services(update, context)
        return
    if text in SERVICE_BUTTONS:
        key, title = SERVICE_BUTTONS[text]
        service_states[uid_s] = {"service": key, "title": title, "created_at": int(time.time())}
        save_db()
        if key == "halloween_candy":
            await safe_reply(
                update,
                f"📋 درخواست {title}\nقیمت فعلی: {format_service_price(key)}\n\n"
                f"{halloween_candy_price_table()}\n\nبرای لغو بنویس: لغو",
            )
        else:
            await safe_reply(
                update,
                f"📋 درخواست {title}\nقیمت فعلی: {format_service_price(key)}\n\n"
                f"جزئیات را در یک پیام بفرست.\nبرای لغو بنویس: لغو",
            )
        return

    if text in ("🛠 مدیریت",) and is_admin(uid):
        await safe_reply(update, "🛠 پنل مدیریت", reply_markup=admin_keyboard())
        return
    if text in ("📊 آمار",) and is_admin(uid):
        users = sum(1 for u in (DB.get("users") or {}).values() if isinstance(u, dict) and u.get("started"))
        subs = len(DB.get("subscriptions") or {})
        await safe_reply(update, f"📊 آمار\nکاربران: {users}\nمقصدها: {subs}")
        return
    if text in ("📡 وضعیت",) and is_admin(uid):
        meta = DB.get("meta") or {}
        await safe_reply(
            update,
            f"📡 وضعیت\n"
            f"آخرین استاک: {meta.get('last_stock_ok_at') or '—'}\n"
            f"آخرین ولیو: {meta.get('last_values_ok_at') or '—'}\n"
            f"ادمین‌ها: {sorted(ADMIN_IDS)}",
        )
        return
    if text in ("🔄 رفرش استاک",) and is_admin(uid):
        try:
            data = await get_stock_cached(force=True)
            for chunk in format_stock_message(data):
                await safe_reply(update, chunk)
        except Exception as exc:
            await safe_reply(update, f"❌ {exc}")
        return
    if text in ("🔄 رفرش ولیو",) and is_admin(uid):
        try:
            s = await get_values_struct(force=True)
            await send_values_cat(update, "fruits", "🍎 میوه\n🤖 LumoNews")
        except Exception as exc:
            await safe_reply(update, f"❌ {exc}")
        return
    if text in ("📣 پیام سراسری",) and is_admin(uid):
        DB.setdefault("support_state", {})[uid_s] = {
            "mode": "awaiting_global_broadcast",
            "created_at": int(time.time()),
        }
        save_db()
        await safe_reply(update, "📣 متن پیام سراسری را بفرست.\nبرای لغو: لغو")
        return


async def monitor_loop(app: Application) -> None:
    log.info("Monitor started")
    last_values = 0.0
    while True:
        try:
            try:
                stock = await asyncio.to_thread(fetch_stock)
                if stock and stock.get("sections"):
                    CACHE["stock"] = stock
                    CACHE["stock_at"] = time.monotonic()
                    sig = stock_content_signature(stock)
                    prev = (DB.get("meta") or {}).get("stock_signature")
                    DB.setdefault("meta", {})["last_stock_ok_at"] = int(time.time())
                    if prev is None:
                        DB["meta"]["stock_signature"] = sig
                        save_db()
                    elif sig != prev:
                        chunks = format_stock_message(stock)
                        prefix = "📈 استاک تغییر کرد!\n"
                        body = [(prefix + chunks[0])] + chunks[1:]
                        for target in collect_broadcast_targets():
                            # only groups/channels (negative ids) auto stock
                            if int(target) >= 0:
                                continue
                            await send_chunks_chat(app.bot, int(target), body)
                        DB["meta"]["stock_signature"] = sig
                        save_db()
                        log.info("Stock change broadcast done")
            except Exception as exc:
                log.warning("stock monitor: %s", exc)

            if time.monotonic() - last_values >= VALUES_POLL_SECONDS:
                last_values = time.monotonic()
                try:
                    structured = await asyncio.to_thread(fetch_values_structured)
                    values = structured.get("all") or {}
                    if len(values) >= 5:
                        prev_snapshot = (DB.get("meta") or {}).get("values_snapshot") or {}
                        prev_values = prev_snapshot.get("all") if isinstance(prev_snapshot, dict) else None
                        CACHE["values_struct"] = structured
                        CACHE["values_at"] = time.monotonic()
                        DB.setdefault("meta", {})["values_snapshot"] = structured
                        DB["meta"]["last_values_ok_at"] = int(time.time())
                        vsig = values_content_signature(values)
                        prev_v = DB["meta"].get("values_signature")
                        if prev_v is None:
                            DB["meta"]["values_signature"] = vsig
                            save_db()
                        elif vsig != prev_v:
                            significant, reason = values_change_significant(prev_values, values)
                            last_bcast = int(DB["meta"].get("values_change_detected_at") or 0)
                            cooled = (int(time.time()) - last_bcast) >= VALUES_BROADCAST_COOLDOWN
                            DB["meta"]["values_signature"] = vsig
                            if significant and cooled:
                                chunks = format_values_category(
                                    structured.get("fruits") or values,
                                    title="🔔 ولیو تغییر کرد!\n🍎 میوه‌ها\n🤖 LumoNews",
                                    footer="🤖 LumoNews",
                                )
                                for target in collect_broadcast_targets():
                                    if int(target) >= 0:
                                        continue
                                    await send_chunks_chat(app.bot, int(target), chunks)
                                DB["meta"]["values_change_detected_at"] = int(time.time())
                                log.info("Values broadcast: %s", reason)
                            else:
                                log.info("Values skip: %s", reason)
                            save_db()
                except Exception as exc:
                    log.warning("values monitor: %s", exc)
        except Exception:
            log.exception("monitor loop")
        await asyncio.sleep(POLL_SECONDS)


async def post_init(app: Application) -> None:
    global MONITOR_STARTED
    if not MONITOR_STARTED:
        MONITOR_STARTED = True
        asyncio.create_task(monitor_loop(app))


def main() -> None:
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing")
    load_db()
    log.info("Starting LumoNews Telegram | admins=%s", sorted(ADMIN_IDS) or "(none — use /setadmin)")
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("setadmin", cmd_setadmin))
    app.add_handler(CommandHandler("stock", cmd_stock))
    app.add_handler(CommandHandler("values", cmd_values))
    app.add_handler(CommandHandler("fruits", cmd_fruits))
    app.add_handler(CommandHandler("permanent", cmd_permanent))
    app.add_handler(CommandHandler("limiteds", cmd_limiteds))
    app.add_handler(CommandHandler("gamepasses", cmd_gamepasses))
    app.add_handler(CommandHandler("services", cmd_services))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("servicereply", cmd_servicereply))
    app.add_handler(CommandHandler("serviceclose", cmd_serviceclose))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
