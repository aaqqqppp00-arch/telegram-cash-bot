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
    """الرد على أمر /start بالعامية المصرية وبدون أي إيموجي"""
    user = update.effective_user
    database.get_or_create_user(user.id, user.first_name, user.username)

    web_url = config.WEB_APP_URL
    if not web_url.startswith("http"):
        web_url = "https://your-domain.com"

    keyboard = [
        [
            InlineKeyboardButton(
                "افتح لعبة WEKI Miner",
                web_app=WebAppInfo(url=web_url)
            )
        ],
        [
            InlineKeyboardButton(
                "إثباتات السحب والدفع",
                callback_data="view_proofs"
            ),
            InlineKeyboardButton(
                "لوحة المتصدرين",
                callback_data="view_leaderboard"
            )
        ],
        [
            InlineKeyboardButton(
                "قناة إثباتات السحب الرسمية",
                url="https://t.me/Sl8_Communit"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        f"أهلاً بيك يا <b>{user.first_name}</b> في لعبة <b>WEKI Miner</b>\n\n"
        "لعبة تعدين وتجميع عملات WEKI:\n"
        "1. اضغط للتعدين وجمع عملات WEKI.\n"
        "2. طور جهاز التعدين بتاعك عشان تضاعف أرباحك.\n"
        "3. اشحن طاقتك مجاناً بمشاهدة الفيديوهات.\n"
        "4. استبدل عملاتك وسيبها على محفظتك في أي وقت.\n\n"
        f"أقل حد للاستبدال: {config.MIN_WITHDRAWAL} جنيه بس!"
    )

    await update.message.reply_html(welcome_text, reply_markup=reply_markup)



async def cmd_proofs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إثباتات الدفع المؤكدة للمستخدمين"""
    proofs = database.get_public_payout_proofs()
    text = "إثباتات الدفع وسجل التحويلات المؤكدة:\n\n"
    for p in proofs[:6]:
        provider_name = {
            "vodafone_cash": "فودافون كاش",
            "orange_cash": "أورنج كاش",
            "etisalat_cash": "اتصالات كاش",
            "we_cash": "وي كاش"
        }.get(p["provider"], p["provider"])
        text += (
            f"عملية #{p['id']}\n"
            f"المستلم: {p['user_name']} ({p['phone_masked']})\n"
            f"المبلغ: {p['amount']:.2f} جنيه عبر {provider_name}\n"
            f"الحالة: تم التحويل بنجاح ({p['time_ago']})\n"
            "----------------------------\n"
        )
    text += "\nجميع التحويلات يتم إرسالها فوراً لمحفظة المستخدم."
    web_url = config.WEB_APP_URL if config.WEB_APP_URL.startswith("http") else "https://your-domain.com"
    keyboard = [
        [InlineKeyboardButton("افتح لعبة WEKI Miner", web_app=WebAppInfo(url=web_url))],
        [InlineKeyboardButton("قناة إثباتات السحب الرسمية", url="https://t.me/Sl8_Communit")]
    ]
    await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض لوحة المتصدرين لأفضل المعدنين"""
    leaders = database.get_leaderboard()
    text = "لوحة المتصدرين لأفضل معدني WEKI Miner:\n\n"
    for l in leaders[:8]:
        text += (
            f"المركز {l['rank']}: <b>{l['name']}</b>\n"
            f"المستوى: {l['level']} | العملات: {l['tokens']:,} $WEKI\n"
            f"إجمالي الأرباح المسحوبة: {l['paid_out']:.2f} جنيه\n\n"
        )
    web_url = config.WEB_APP_URL if config.WEB_APP_URL.startswith("http") else "https://your-domain.com"
    keyboard = [
        [InlineKeyboardButton("افتح لعبة WEKI Miner", web_app=WebAppInfo(url=web_url))],
        [InlineKeyboardButton("قناة إثباتات السحب الرسمية", url="https://t.me/Sl8_Communit")]
    ]
    await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المسؤول لعرض الإحصائيات وطلبات السحب المعلقة"""
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID and config.ADMIN_ID != 0:
        await update.message.reply_text("الأمر ده مخصص للمسؤول بس.")
        return

    stats = database.get_system_stats()
    pending = database.get_pending_withdrawals()

    text = (
        "لوحة تحكم المسؤول (أرباح كاش):\n\n"
        f"عدد المستخدمين: <b>{stats['total_users']}</b>\n"
        f"إجمالي الإعلانات اللي اتسجلت: <b>{stats['total_ads'] or 0}</b>\n"
        f"إجمالي الفلوس اللي اتجمعت: <b>{(stats['total_paid_out'] or 0):.2f} جنيه</b>\n"
        f"طلبات السحب اللي مستنية موافقة: <b>{stats['pending_withdrawals']}</b>\n"
    )

    await update.message.reply_html(text)

    # عرض الطلبات المعلقة إن وجدت
    if pending:
        for req in pending[:5]:
            p_name = {
                "vodafone_cash": "فودافون كاش",
                "orange_cash": "أورنج كاش",
                "etisalat_cash": "اتصالات كاش",
                "we_cash": "وي كاش"
            }.get(req["provider"], req["provider"])

            req_text = (
                f"طلب سحب رقم #{req['id']}\n"
                f"المستخدم: @{req.get('username') or 'من غير يوزر'} (الآيدي: <code>{req['telegram_id']}</code>)\n"
                f"المحفظة: <b>{p_name}</b>\n"
                f"الرقم: <code>{req['phone_number']}</code>\n"
                f"المبلغ: <b>{req['amount']:.2f} جنيه</b>"
            )
            buttons = [
                [
                    InlineKeyboardButton("تم التحويل (تأكيد)", callback_data=f"appr_{req['id']}"),
                    InlineKeyboardButton("رفض وإرجاع الفلوس", callback_data=f"rejc_{req['id']}")
                ]
            ]
            await update.message.reply_html(req_text, reply_markup=InlineKeyboardMarkup(buttons))



async def handle_public_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغطات أزرار إثباتات الدفع والمتصدرين لجميع المستخدمين"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "view_proofs":
        proofs = database.get_public_payout_proofs()
        text = "إثباتات وتأكيدات الدفع الحية لمستخدمي WEKI Miner:\n\n"
        for p in proofs[:6]:
            provider_name = {
                "vodafone_cash": "فودافون كاش",
                "orange_cash": "أورنج كاش",
                "etisalat_cash": "اتصالات كاش",
                "we_cash": "وي كاش"
            }.get(p["provider"], p["provider"])
            text += (
                f"عملية رقم: <b>{p['id']}</b>\n"
                f"المستلم: <b>{p['user_name']}</b> ({p['phone_masked']})\n"
                f"المبلغ: <b>{p['amount']:.2f} جنيه</b> عبر {provider_name}\n"
                f"الحالة: تم التحويل بنجاح ({p['time_ago']})\n"
                "----------------------------\n"
            )
        text += "\nجميع التحويلات يتم إرسالها فوراً لمحافظ الكاش."
        web_url = config.WEB_APP_URL if config.WEB_APP_URL.startswith("http") else "https://your-domain.com"
        keyboard = [
        [InlineKeyboardButton("افتح لعبة WEKI Miner", web_app=WebAppInfo(url=web_url))],
        [InlineKeyboardButton("قناة إثباتات السحب الرسمية", url="https://t.me/Sl8_Communit")]
    ]
        await query.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "view_leaderboard":
        leaders = database.get_leaderboard()
        text = "لوحة المتصدرين لأفضل معدني WEKI Miner:\n\n"
        for l in leaders[:8]:
            text += (
                f"المركز {l['rank']}: <b>{l['name']}</b>\n"
                f"المستوى: {l['level']} | العملات: {l['tokens']:,} $WEKI\n"
                f"إجمالي الأرباح المسحوبة: {l['paid_out']:.2f} جنيه\n\n"
            )
        web_url = config.WEB_APP_URL if config.WEB_APP_URL.startswith("http") else "https://your-domain.com"
        keyboard = [
        [InlineKeyboardButton("افتح لعبة WEKI Miner", web_app=WebAppInfo(url=web_url))],
        [InlineKeyboardButton("قناة إثباتات السحب الرسمية", url="https://t.me/Sl8_Communit")]
    ]
        await query.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التعامل مع ضغطات أزرار الموافقة والرفض من المسؤول بدون إيموجي"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID and config.ADMIN_ID != 0:
        await query.edit_message_text("مش مسموحلك تنفذ الخطوة دي.")
        return

    action, req_id_str = data.split("_")
    req_id = int(req_id_str)

    new_status = "approved" if action == "appr" else "rejected"
    success, withdrawal = database.update_withdrawal_status(req_id, new_status)

    if not success:
        await query.edit_message_text("الطلب ده اتنفذ قبل كده أو مش موجود.")
        return

    p_name = {
        "vodafone_cash": "فودافون كاش",
        "orange_cash": "أورنج كاش",
        "etisalat_cash": "اتصالات كاش",
        "we_cash": "وي كاش"
    }.get(withdrawal["provider"], withdrawal["provider"])

    if new_status == "approved":
        await query.edit_message_text(
            f"تم تأكيد تحويل الطلب #{req_id} بنجاح.\n"
            f"المبلغ: {withdrawal['amount']:.2f} جنيه على رقم {withdrawal['phone_number']} ({p_name})",
            parse_mode="HTML"
        )
        # نشر إثبات السحب تلقائياً في القناة العامة
        try:
            proof_text = (
                "إثبات سحب جديد تم تحويله بنجاح:\n\n"
                f"المبلغ: <b>{withdrawal['amount']:.2f} جنيه</b>\n"
                f"المحفظة: <b>{p_name}</b>\n"
                f"المستلم: <code>{withdrawal['phone_number'][:3]}*****{withdrawal['phone_number'][-3:]}</code>\n"
                f"كود العملية: <code>WKM-{withdrawal['id'] + 8420}</code>\n"
                f"الحالة: تم التحويل بنجاح\n\n"
                "العب واجمع عملاتك واسحب كاش عبر @Weki_earn_bot"
            )
            await context.bot.send_message(chat_id="@Sl8_Communit", text=proof_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Could not post to proofs channel: {e}")

        # إشعار المستخدم بنجاح التحويل
        try:
            await context.bot.send_message(
                chat_id=withdrawal["telegram_id"],
                text=(
                    "ألف مبروك! تم تحويل فلوسك بنجاح.\n\n"
                    f"المبلغ: <b>{withdrawal['amount']:.2f} جنيه</b>\n"
                    f"المحفظة: <b>{p_name}</b>\n"
                    f"الرقم: <b>{withdrawal['phone_number']}</b>\n\n"
                    "شكراً لوجودك معانا، تقدر تكمل تعدين وتجمع عملات وتسحب تاني في أي وقت."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify user {withdrawal['telegram_id']}: {e}")

    else:
        await query.edit_message_text(
            f"تم رفض الطلب #{req_id} والفلوس رجعت ({withdrawal['amount']:.2f} جنيه) لرصيد المستخدم.",
            parse_mode="HTML"
        )
        # إشعار المستخدم بالرفض
        try:
            await context.bot.send_message(
                chat_id=withdrawal["telegram_id"],
                text=(
                    "تنبيه بخصوص طلب السحب:\n\n"
                    f"طلب السحب بتاعك بمبلغ <b>{withdrawal['amount']:.2f} جنيه</b> اترفض والفلوس رجعت بالكامل لرصيدك في التطبيق.\n"
                    "أتأكد إن رقم المحفظة شغال ومظبوط وجرب تسحب تاني."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify user {withdrawal['telegram_id']}: {e}")


# ربط أوامر البوت
if bot_app:
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("admin", cmd_admin))
    bot_app.add_handler(CommandHandler("proofs", cmd_proofs))
    bot_app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    bot_app.add_handler(CallbackQueryHandler(handle_public_callback, pattern=r"^view_"))
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
    return FileResponse(str(BASE_DIR / "static" / "index.html"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@api_app.get("/style.css")
async def get_css():
    return FileResponse(str(BASE_DIR / "static" / "style.css"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@api_app.get("/app.js")
async def get_js():
    return FileResponse(str(BASE_DIR / "static" / "app.js"), headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# --- نماذج الـ API ---

class TapRequest(BaseModel):
    count: Optional[int] = 1

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
            "tokens_per_egp": config.TOKENS_PER_EGP,
            "adsgram_block_id": config.ADSGRAM_BLOCK_ID
        }
    }

@api_app.post("/api/tap")
async def api_tap(body: Optional[TapRequest] = None, x_telegram_init_data: Optional[str] = Header(None)):
    """الضغط للتعدين في اللعبة (يدعم تجميع الضغطات)"""
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]
    count = body.count if body and body.count else 1

    success, message, user = database.process_mining_tap(telegram_id, count=count)
    return {
        "success": success,
        "message": message,
        "user": user
    }

@api_app.post("/api/upgrade")
async def api_upgrade(x_telegram_init_data: Optional[str] = Header(None)):
    """ترقية مستوى التعدين بالعملات"""
    user_info = get_authenticated_user(x_telegram_init_data)
    telegram_id = user_info["id"]

    success, message, user = database.upgrade_miner_level(telegram_id)
    return {
        "success": success,
        "message": message,
        "user": user
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

    user = database.get_user(telegram_id)
    return {
        "success": success,
        "message": message,
        "new_balance": new_balance,
        "user": user
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
            f"طلب سحب جديد #{withdrawal_id}!\n\n"
            f"المستخدم: @{username} (الآيدي: <code>{telegram_id}</code>)\n"
            f"المحفظة: <b>{p_name}</b>\n"
            f"رقم الكاش: <code>{body.phone_number}</code>\n"
            f"المبلغ: <b>{body.amount:.2f} جنيه</b>"
        )
        buttons = [
            [
                InlineKeyboardButton("تم التحويل (تأكيد)", callback_data=f"appr_{withdrawal_id}"),
                InlineKeyboardButton("رفض وإرجاع الفلوس", callback_data=f"rejc_{withdrawal_id}")
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


@api_app.get("/api/proofs")
async def api_proofs():
    """عرض إثباتات الدفع المؤكدة للجمهور (متوافق مع البند 8)"""
    return {"success": True, "proofs": database.get_public_payout_proofs()}

@api_app.get("/api/leaderboard")
async def api_leaderboard():
    """عرض لوحة المتصدرين للجمهور (متوافق مع البند 8)"""
    return {"success": True, "leaderboard": database.get_leaderboard()}

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
