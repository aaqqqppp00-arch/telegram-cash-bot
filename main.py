import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

import config
import database
from auth import validate_telegram_init_data

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة قاعدة البيانات
database.init_db()

# بناء تطبيق البوت
bot_app: Optional[Application] = None
if config.BOT_TOKEN and config.BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
    bot_app = Application.builder().token(config.BOT_TOKEN).build()


# --- أوامر البوت ---

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على أمر /start بفتح الميني آب وتوجيه المستخدم"""
    user = update.effective_user
    database.get_or_create_user(user.id, user.first_name, user.username)

    web_url = config.WEB_APP_URL
    if not web_url.startswith("http"):
        web_url = "https://your-domain.com"

    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 اضغط هنا لفتح محفظة الأرباح",
                web_app=WebAppInfo(url=web_url)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"أهلاً بك يا <b>{user.first_name}</b> في بوت <b>أرباح كاش</b> 💰\n\n"
        "📱 <b>كيف تربح من البوت؟</b>\n"
        "1. افتح التطبيق بالضغط على الزر بالأسفل.\n"
        "2. شاهد الإعلانات واجمع الأرباح فوراً.\n"
        "3. اسحب أرباحك على محفظتك (فودافون كاش، أورنج كاش، اتصالات كاش، وي كاش).\n\n"
        f"💵 <b>المكافأة:</b> {config.REWARD_PER_AD} ج لكل إعلان.\n"
        f"💳 <b>الحد الأدنى للسحب:</b> {config.MIN_WITHDRAWAL} ج فقط!"
    )

    await update.message.reply_html(welcome_text, reply_markup=reply_markup)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المسؤول لعرض الإحصائيات وطلبات السحب المعلقة"""
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID and config.ADMIN_ID != 0:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للمسؤول فقط.")
        return

    stats = database.get_system_stats()
    pending = database.get_pending_withdrawals()

    text = (
        "📊 <b>لوحة تحكم المسؤول (أرباح كاش):</b>\n\n"
        f"👥 إجمالي المستخدمين: <b>{stats['total_users']}</b>\n"
        f"📺 إجمالي الإعلانات المشاهدة: <b>{stats['total_ads'] or 0}</b>\n"
        f"💰 إجمالي الأرباح المكتسبة: <b>{(stats['total_paid_out'] or 0):.2f} ج</b>\n"
        f"⏳ طلبات السحب المعلقة: <b>{stats['pending_withdrawals']}</b>\n"
    )

    await update.message.reply_html(text)

    # عرض الطلبات المعلقة إن وجدت
    if pending:
        for req in pending[:5]: # عرض أول 5 طلبات
            p_name = {
                "vodafone_cash": "فودافون كاش",
                "orange_cash": "أورنج كاش",
                "etisalat_cash": "اتصالات كاش",
                "we_cash": "وي كاش"
            }.get(req["provider"], req["provider"])

            req_text = (
                f"🚨 <b>طلب سحب رقم #{req['id']}</b>\n"
                f"المستخدم: @{req.get('username') or 'بدون'} (ID: <code>{req['telegram_id']}</code>)\n"
                f"المحفظة: <b>{p_name}</b>\n"
                f"الرقم: <code>{req['phone_number']}</code>\n"
                f"المبلغ: <b>{req['amount']:.2f} ج</b>"
            )
            buttons = [
                [
                    InlineKeyboardButton("✅ تم التحويل (تأكيد)", callback_data=f"appr_{req['id']}"),
                    InlineKeyboardButton("❌ رفض وإرجاع الرصيد", callback_data=f"rejc_{req['id']}")
                ]
            ]
            await update.message.reply_html(req_text, reply_markup=InlineKeyboardMarkup(buttons))


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغطات أزرار الموافقة والرفض من المسؤول"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID and config.ADMIN_ID != 0:
        await query.edit_message_text("غير مسموح لك بتنفيذ هذا الإجراء.")
        return

    action, req_id_str = data.split("_")
    req_id = int(req_id_str)

    new_status = "approved" if action == "appr" else "rejected"
    success, withdrawal = database.update_withdrawal_status(req_id, new_status)

    if not success:
        await query.edit_message_text("⚠️ هذا الطلب تم اتخاذ إجراء عليه مسبقاً أو غير موجود.")
        return

    p_name = {
        "vodafone_cash": "فودافون كاش",
        "orange_cash": "أورنج كاش",
        "etisalat_cash": "اتصالات كاش",
        "we_cash": "وي كاش"
    }.get(withdrawal["provider"], withdrawal["provider"])

    if new_status == "approved":
        await query.edit_message_text(
            f"✅ <b>تم تأكيد تحويل الطلب #{req_id} بنجاح!</b>\n"
            f"المبلغ: {withdrawal['amount']:.2f} ج على رقم {withdrawal['phone_number']} ({p_name})",
            parse_mode="HTML"
        )
        # إشعار المستخدم بنجاح التحويل
        try:
            await context.bot.send_message(
                chat_id=withdrawal["telegram_id"],
                text=(
                    "🎉 <b>مبروك! تم تحويل أرباحك بنجاح!</b>\n\n"
                    f"💵 المبلغ: <b>{withdrawal['amount']:.2f} ج</b>\n"
                    f"📱 المحفظة: <b>{p_name}</b>\n"
                    f"📞 الرقم: <b>{withdrawal['phone_number']}</b>\n\n"
                    "شكراً لعملك معنا! يمكنك الاستمرار بمشاهدة المزيد من الإعلانات لسحب مبالغ جديدة 🚀"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify user {withdrawal['telegram_id']}: {e}")

    else:
        await query.edit_message_text(
            f"❌ <b>تم رفض الطلب #{req_id} وإرجاع المبلغ ({withdrawal['amount']:.2f} ج) لرصيد المستخدم.</b>",
            parse_mode="HTML"
        )
        # إشعار المستخدم بالرفض
        try:
            await context.bot.send_message(
                chat_id=withdrawal["telegram_id"],
                text=(
                    "⚠️ <b>تنبيه بخصوص طلب السحب:</b>\n\n"
                    f"تم رفض طلب السحب بمبلغ <b>{withdrawal['amount']:.2f} ج</b> وتمت إعادة المبلغ بالكامل إلى رصيدك.\n"
                    "يرجى التأكد من كتابة رقم محفظة صحيح ومفعل وحاول مجدداً."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify user {withdrawal['telegram_id']}: {e}")


# ربط أوامر البوت
if bot_app:
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("admin", cmd_admin))
    bot_app.add_handler(CallbackQueryHandler(handle_admin_callback, pattern=r"^(appr|rejc)_"))


# --- إعداد تطبيق FastAPI ودورة الحياة (Lifespan) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    if bot_app:
        logger.info("Starting Telegram Bot polling...")
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
    yield
    if bot_app:
        logger.info("Stopping Telegram Bot...")
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

api_app = FastAPI(lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent

# ربط الملفات الثابتة (HTML, CSS, JS)
api_app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@api_app.get("/")
async def get_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@api_app.get("/style.css")
async def get_css():
    return FileResponse(str(BASE_DIR / "static" / "style.css"))

@api_app.get("/app.js")
async def get_js():
    return FileResponse(str(BASE_DIR / "static" / "app.js"))


# --- نماذج الـ API ---

class WithdrawRequest(BaseModel):
    provider: str
    phone_number: str
    amount: float

def get_authenticated_user(x_telegram_init_data: Optional[str] = Header(None)):
    """فحص بيانات التيليجرام واستخراج هوية المستخدم"""
    if not x_telegram_init_data:
        # وضع تجريبي محلي إذا لم ترسل ترويسة
        return {"id": 999999999, "first_name": "مستخدم تجريبي", "username": "test_user"}
        
    user_info = validate_telegram_init_data(x_telegram_init_data)
    if not user_info:
        raise HTTPException(status_code=401, detail="بيانات تليجرام غير صالحة")
    return user_info


# --- نقاط نهاية الـ API (Endpoints) ---

@api_app.get("/api/user-info")
async def api_user_info(x_telegram_init_data: Optional[str] = Header(None)):
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]
    first_name = user_info.get("first_name", "")
    username = user_info.get("username", "")

    user = database.get_or_create_user(telegram_id, first_name, username)
    return {
        "success": True,
        "user": user,
        "config": {
            "reward_per_ad": config.REWARD_PER_AD,
            "min_withdrawal": config.MIN_WITHDRAWAL,
            "adsgram_block_id": config.ADSGRAM_BLOCK_ID
        }
    }

@api_app.post("/api/claim-ad")
async def api_claim_ad(x_telegram_init_data: Optional[str] = Header(None)):
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]

    success, message, new_balance = database.claim_ad_reward(
        telegram_id=telegram_id,
        reward=config.REWARD_PER_AD,
        cooldown_seconds=config.AD_COOLDOWN_SECONDS
    )

    return {
        "success": success,
        "message": message,
        "new_balance": new_balance
    }

@api_app.get("/api/adsgram-reward")
async def api_adsgram_reward(userid: Optional[int] = None):
    """Webhook اختياري لـ Adsgram لإضافة المكافأة مباشرة من السيرفر"""
    if userid:
        success, message, new_balance = database.claim_ad_reward(
            telegram_id=userid,
            reward=config.REWARD_PER_AD,
            cooldown_seconds=config.AD_COOLDOWN_SECONDS
        )
        return {"ok": True, "rewarded": success, "new_balance": new_balance}
    return {"ok": False, "error": "missing userid"}

@api_app.post("/api/withdraw")
async def api_withdraw(body: WithdrawRequest, x_telegram_init_data: Optional[str] = Header(None)):
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]
    username = user_info.get("username", "بدون معرف")

    success, message, withdrawal_id = database.create_withdrawal(
        telegram_id=telegram_id,
        provider=body.provider,
        phone_number=body.phone_number,
        amount=body.amount,
        min_amount=config.MIN_WITHDRAWAL
    )

    if success and withdrawal_id and bot_app and config.ADMIN_ID != 0:
        # إرسال إشعار فوري للمسؤول على تليجرام
        p_name = {
            "vodafone_cash": "فودافون كاش",
            "orange_cash": "أورنج كاش",
            "etisalat_cash": "اتصالات كاش",
            "we_cash": "وي كاش"
        }.get(body.provider, body.provider)

        notify_text = (
            f"🚨 <b>طلب سحب جديد #{withdrawal_id}!</b>\n\n"
            f"👤 المستخدم: @{username} (ID: <code>{telegram_id}</code>)\n"
            f"💳 المحفظة: <b>{p_name}</b>\n"
            f"📞 رقم الكاش: <code>{body.phone_number}</code>\n"
            f"💵 المبلغ: <b>{body.amount:.2f} جنيه</b>"
        )
        buttons = [
            [
                InlineKeyboardButton("✅ تم التحويل (تأكيد)", callback_data=f"appr_{withdrawal_id}"),
                InlineKeyboardButton("❌ رفض وإرجاع الرصيد", callback_data=f"rejc_{withdrawal_id}")
            ]
        ]
        try:
            await bot_app.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=notify_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin about withdrawal #{withdrawal_id}: {e}")

    return {
        "success": success,
        "message": message,
        "withdrawal_id": withdrawal_id
    }

@api_app.get("/api/withdrawals")
async def api_withdrawals(x_telegram_init_data: Optional[str] = Header(None)):
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]
    history = database.get_user_withdrawals(telegram_id)
    return {
        "success": True,
        "withdrawals": history
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:api_app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=False)
