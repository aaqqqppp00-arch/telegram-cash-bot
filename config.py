import os
from pathlib import Path

# تحميل المتغيرات من ملف .env تلقائياً إذا وُجد
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# Telegram Bot Token (من BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Telegram User ID الخاص بك كمسؤول لتصلك إشعارات السحب
# يمكنك الحصول عليه من بوت مثل @userinfobot
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# معرف الإعلان من Adsgram (Block ID)
ADSGRAM_BLOCK_ID = os.getenv("ADSGRAM_BLOCK_ID", "46937")

# المكافأة لكل إعلان مكتمل بالجنيه المصري (مثال: 0.05 = 5 قروش)
REWARD_PER_AD = float(os.getenv("REWARD_PER_AD", "0.05"))

# الحد الأدنى للسحب بالجنيه المصري
MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", "20.0"))

# معدل تحويل عملات اللعبة للجنيه (مثال: 5000 عملة = 1 جنيه مصري)
TOKENS_PER_EGP = int(os.getenv("TOKENS_PER_EGP", "5000"))

# وقت الانتظار الأدنى بين الإعلانات بالثواني (لمنع التلاعب)
AD_COOLDOWN_SECONDS = int(os.getenv("AD_COOLDOWN_SECONDS", "15"))

# رابط الدومين أو السيرفر الذي يعمل عليه التطبيق المصغر (Mini App URL)
# مثال: https://my-bot-app.loca.lt أو الدومين الخاص بك مع HTTPS
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-domain.com")

# إعدادات السيرفر
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
