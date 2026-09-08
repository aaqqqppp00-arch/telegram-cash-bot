import hmac
import hashlib
import json
import urllib.parse
from typing import Optional, Dict, Any
from config import BOT_TOKEN

def validate_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """
    التحقق من صحة initData القادمة من Telegram WebApp لمنع تزوير الطلبات
    """
    if not init_data:
        return None
        
    # إذا كان التوكن تجريبياً ولم يتم تغييره بعد، نقوم بفك البيانات مباشرة للتسهيل
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        try:
            parsed = dict(urllib.parse.parse_qsl(init_data))
            if "user" in parsed:
                return json.loads(parsed["user"])
        except Exception:
            return None

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        received_hash = parsed_data.pop("hash", None)
        if not received_hash:
            return None
            
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # حساب المفتاح السري
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(calculated_hash, received_hash):
            user_data_str = parsed_data.get("user")
            if user_data_str:
                return json.loads(user_data_str)
        return None
    except Exception as e:
        print(f"Error validating initData: {e}")
        return None
