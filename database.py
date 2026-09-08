import config
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

DB_PATH = str(Path(__file__).resolve().parent / "cash_bot.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # جدول المستخدمين
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            balance REAL DEFAULT 0.0,
            tokens INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 100,
            max_energy INTEGER DEFAULT 100,
            miner_level INTEGER DEFAULT 1,
            last_energy_timestamp INTEGER DEFAULT 0,
            total_earned REAL DEFAULT 0.0,
            total_ads_watched INTEGER DEFAULT 0,
            last_ad_timestamp INTEGER DEFAULT 0,
            joined_at INTEGER
        );
        """)

        # إضافة الأعمدة لو كان الجدول قديماً (Migration)
        existing_cols = [col[1] for col in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if "tokens" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN tokens INTEGER DEFAULT 0")
        if "energy" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN energy INTEGER DEFAULT 100")
        if "max_energy" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN max_energy INTEGER DEFAULT 100")
        if "miner_level" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN miner_level INTEGER DEFAULT 1")
        if "last_energy_timestamp" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN last_energy_timestamp INTEGER DEFAULT 0")

        # جدول طلبات السحب
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            created_at INTEGER NOT NULL,
            reviewed_at INTEGER,
            FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
        );
        """)

        # جدول سجل مكافآت الإعلانات
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ad_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            reward REAL NOT NULL,
            watched_at INTEGER NOT NULL
        );
        """)
        conn.commit()

def calculate_energy(user: Dict[str, Any]) -> int:
    """إعادة شحن الطاقة تدريجياً مع مرور الوقت (نقطة كل 3 ثواني)"""
    now = int(time.time())
    last_time = user.get("last_energy_timestamp") or now
    elapsed = max(0, now - last_time)
    current_energy = user.get("energy", 100)
    max_energy = user.get("max_energy", 100)
    
    recovered = elapsed // 3 # استرجاع نقطة طاقة كل 3 ثواني
    new_energy = min(max_energy, current_energy + recovered)
    return new_energy

def get_or_create_user(telegram_id: int, first_name: str = "", username: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        now = int(time.time())
        if row is None:
            cursor.execute("""
            INSERT INTO users (telegram_id, first_name, username, balance, tokens, energy, max_energy, miner_level, last_energy_timestamp, total_earned, total_ads_watched, last_ad_timestamp, joined_at)
            VALUES (?, ?, ?, 0.0, 0, 100, 100, 1, ?, 0.0, 0, 0, ?)
            """, (telegram_id, first_name, username or "", now, now))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
        else:
            cursor.execute("""
            UPDATE users SET first_name = ?, username = ? WHERE telegram_id = ?
            """, (first_name, username or "", telegram_id))
            conn.commit()
            
        user_dict = dict(row)
        user_dict["energy"] = calculate_energy(user_dict)
        return user_dict

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        if not row:
            return None
        user_dict = dict(row)
        user_dict["energy"] = calculate_energy(user_dict)
        return user_dict

def process_mining_tap(telegram_id: int, count: int = 1) -> Tuple[bool, str, Dict[str, Any]]:
    """الضغط للتعدين في اللعبة: استهلاك الطاقة وإضافة عملات WEKI (يدعم تجميع الضغطات)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        if not row:
            return False, "المستخدم غير موجود", {}

        user = dict(row)
        energy = calculate_energy(user)
        miner_level = user.get("miner_level", 1)
        tokens = user.get("tokens", 0)

        if energy <= 0:
            return False, "طاقتك خلصت! اشحن الطاقة مجاناً بمشاهدة فيديو أو انتظر شوية.", user

        # تحديد عدد الضغطات المسموح بتنفيذها حسب الطاقة المتاحة
        valid_count = max(1, min(int(count), 50))
        taps_to_process = min(energy, valid_count)

        coins_gained = taps_to_process * miner_level
        new_energy = max(0, energy - taps_to_process)
        new_tokens = tokens + coins_gained
        now = int(time.time())

        # تحديث رصيد الكاش تلقائياً (100 عملة = 1 جنيه)
        new_balance = round(new_tokens / float(config.TOKENS_PER_EGP), 2)

        cursor.execute("""
        UPDATE users 
        SET energy = ?, tokens = ?, balance = ?, last_energy_timestamp = ?
        WHERE telegram_id = ?
        """, (new_energy, new_tokens, new_balance, now, telegram_id))
        conn.commit()

        user["energy"] = new_energy
        user["tokens"] = new_tokens
        user["balance"] = new_balance
        return True, "تم التعدين بنجاح", user

def upgrade_miner_level(telegram_id: int) -> Tuple[bool, str, Dict[str, Any]]:
    """ترقية مستوى التعدين باستخدام العملات المجمعة"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        if not row:
            return False, "المستخدم غير موجود", {}

        user = dict(row)
        level = user.get("miner_level", 1)
        tokens = user.get("tokens", 0)
        upgrade_cost = level * 100 # تكلفة الترقية

        if tokens < upgrade_cost:
            return False, f"محتاج {upgrade_cost} عملة للترقية، رصيدك الحالي مش كفاية.", user

        new_level = level + 1
        new_tokens = tokens - upgrade_cost
        new_balance = round(new_tokens / float(config.TOKENS_PER_EGP), 2)
        new_max_energy = 100 + (new_level - 1) * 20

        cursor.execute("""
        UPDATE users 
        SET miner_level = ?, tokens = ?, balance = ?, max_energy = ?
        WHERE telegram_id = ?
        """, (new_level, new_tokens, new_balance, new_max_energy, telegram_id))
        conn.commit()

        user["miner_level"] = new_level
        user["tokens"] = new_tokens
        user["balance"] = new_balance
        user["max_energy"] = new_max_energy
        return True, f"تمت الترقية للمستوى {new_level} بنجاح!", user

def claim_ad_reward(telegram_id: int, reward: float, cooldown_seconds: int = 15) -> Tuple[bool, str, float]:
    """شحن الطاقة بالكامل وإضافة مكافأة الفيديو"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "المستخدم غير موجود", 0.0
            
        user = dict(row)
        now = int(time.time())
        last_ad_time = user["last_ad_timestamp"]
        elapsed = now - last_ad_time
        
        if elapsed < cooldown_seconds:
            wait_left = cooldown_seconds - elapsed
            return False, f"يرجى الانتظار {wait_left} ثانية قبل مشاهدة الفيديو التالي", user["balance"]
            
        bonus_tokens = 50 # 5 عملات إضافية
        new_tokens = user.get("tokens", 0) + bonus_tokens
        new_balance = round(new_tokens / float(config.TOKENS_PER_EGP), 2)
        new_total_earned = round(user["total_earned"] + reward, 2)
        new_ads_count = user["total_ads_watched"] + 1
        max_energy = user.get("max_energy", 100)

        cursor.execute("""
        UPDATE users 
        SET balance = ?, tokens = ?, energy = ?, total_earned = ?, total_ads_watched = ?, last_ad_timestamp = ?, last_energy_timestamp = ?
        WHERE telegram_id = ?
        """, (new_balance, new_tokens, max_energy, new_total_earned, new_ads_count, now, now, telegram_id))
        
        cursor.execute("""
        INSERT INTO ad_logs (telegram_id, reward, watched_at)
        VALUES (?, ?, ?)
        """, (telegram_id, reward, now))
        
        conn.commit()
        return True, "تم شحن الطاقة بالكامل وإضافة المكافأة!", new_balance

def create_withdrawal(telegram_id: int, provider: str, phone_number: str, amount: float, min_amount: float) -> Tuple[bool, str, Optional[int]]:
    phone_clean = phone_number.strip().replace(" ", "").replace("-", "")
    if len(phone_clean) != 11 or not (phone_clean.startswith("010") or phone_clean.startswith("011") or phone_clean.startswith("012") or phone_clean.startswith("015")):
        return False, "رقم الموبايل غير صحيح! لازم يبدأ بـ 010 أو 011 أو 012 أو 015 ومكون من 11 رقم", None
        
    if amount < min_amount:
        return False, f"أقل حد للسحب هو {min_amount} جنيه", None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, tokens FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "المستخدم غير موجود", None
            
        current_balance = row["balance"]
        if current_balance < amount:
            return False, f"رصيدك الحالي ({current_balance:.2f} ج) ميكفيش تسحب ({amount:.2f} ج)", None
            
        cursor.execute("SELECT id FROM withdrawals WHERE telegram_id = ? AND status = 'pending'", (telegram_id,))
        if cursor.fetchone():
            return False, "عندك طلب سحب سابق لسه بيتراجع، استنى لما يخلص.", None
            
        new_balance = round(current_balance - amount, 2)
        new_tokens = int(new_balance * config.TOKENS_PER_EGP)
        now = int(time.time())
        
        cursor.execute("UPDATE users SET balance = ?, tokens = ? WHERE telegram_id = ?", (new_balance, new_tokens, telegram_id))
        
        cursor.execute("""
        INSERT INTO withdrawals (telegram_id, provider, phone_number, amount, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """, (telegram_id, provider, phone_clean, amount, now))
        
        withdrawal_id = cursor.lastrowid
        conn.commit()
        
        return True, "تم إرسال طلب السحب بنجاح! هيتم تحويل المبلغ قريباً.", withdrawal_id

def get_user_withdrawals(telegram_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE telegram_id = ? ORDER BY id DESC LIMIT 20", (telegram_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_pending_withdrawals() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT w.*, u.username, u.first_name 
        FROM withdrawals w 
        JOIN users u ON w.telegram_id = u.telegram_id 
        WHERE w.status = 'pending' 
        ORDER BY w.id ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

def update_withdrawal_status(withdrawal_id: int, new_status: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, None
            
        withdrawal = dict(row)
        if withdrawal["status"] != "pending":
            return False, withdrawal
            
        now = int(time.time())
        
        if new_status == "rejected":
            refund = withdrawal["amount"]
            refund_tokens = int(refund * 100)
            cursor.execute("""
            UPDATE users SET balance = balance + ?, tokens = tokens + ? WHERE telegram_id = ?
            """, (refund, refund_tokens, withdrawal["telegram_id"]))
            
        cursor.execute("UPDATE withdrawals SET status = ?, reviewed_at = ? WHERE id = ?", (new_status, now, withdrawal_id))
        conn.commit()
        withdrawal["status"] = new_status
        return True, withdrawal

def get_system_stats() -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_users, SUM(balance) AS total_balance, SUM(total_earned) AS total_paid_out, SUM(total_ads_watched) AS total_ads, SUM(tokens) AS total_tokens FROM users")
        stats = dict(cursor.fetchone())
        
        cursor.execute("SELECT COUNT(*) AS pending_count FROM withdrawals WHERE status = 'pending'")
        stats["pending_withdrawals"] = cursor.fetchone()["pending_count"]
        return stats
