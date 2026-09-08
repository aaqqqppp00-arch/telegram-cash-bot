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
            total_earned REAL DEFAULT 0.0,
            total_ads_watched INTEGER DEFAULT 0,
            last_ad_timestamp INTEGER DEFAULT 0,
            joined_at INTEGER
        );
        """)
        
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

        # جدول سجل مكافآت الإعلانات (للتدقيق ومنع الاحتيال)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ad_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            reward REAL NOT NULL,
            watched_at INTEGER NOT NULL
        );
        """)
        conn.commit()

def get_or_create_user(telegram_id: int, first_name: str = "", username: str = "") -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        now = int(time.time())
        if row is None:
            cursor.execute("""
            INSERT INTO users (telegram_id, first_name, username, balance, total_earned, total_ads_watched, last_ad_timestamp, joined_at)
            VALUES (?, ?, ?, 0.0, 0.0, 0, 0, ?)
            """, (telegram_id, first_name, username or "", now))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
        else:
            # تحديث الاسم والمعرف إذا تغير
            cursor.execute("""
            UPDATE users SET first_name = ?, username = ? WHERE telegram_id = ?
            """, (first_name, username or "", telegram_id))
            conn.commit()
            
        return dict(row)

def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def claim_ad_reward(telegram_id: int, reward: float, cooldown_seconds: int = 15) -> Tuple[bool, str, float]:
    """
    تحقق من وقت الانتظار ثم أضف المكافأة للمستخدم
    ترجع: (نجاح/فشل, الرسالة, الرصيد الجديد)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance, total_earned, total_ads_watched, last_ad_timestamp FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "المستخدم غير موجود", 0.0
            
        now = int(time.time())
        last_ad_time = row["last_ad_timestamp"]
        elapsed = now - last_ad_time
        
        if elapsed < cooldown_seconds:
            wait_left = cooldown_seconds - elapsed
            return False, f"يرجى الانتظار {wait_left} ثانية قبل مشاهدة الإعلان التالي", row["balance"]
            
        new_balance = round(row["balance"] + reward, 2)
        new_total_earned = round(row["total_earned"] + reward, 2)
        new_ads_count = row["total_ads_watched"] + 1
        
        cursor.execute("""
        UPDATE users 
        SET balance = ?, total_earned = ?, total_ads_watched = ?, last_ad_timestamp = ?
        WHERE telegram_id = ?
        """, (new_balance, new_total_earned, new_ads_count, now, telegram_id))
        
        cursor.execute("""
        INSERT INTO ad_logs (telegram_id, reward, watched_at)
        VALUES (?, ?, ?)
        """, (telegram_id, reward, now))
        
        conn.commit()
        return True, "تمت إضافة المكافأة بنجاح!", new_balance

def create_withdrawal(telegram_id: int, provider: str, phone_number: str, amount: float, min_amount: float) -> Tuple[bool, str, Optional[int]]:
    """
    خصم الرصيد وإنشاء طلب سحب جديد
    ترجع: (نجاح/فشل, رسالة, معرّف الطلب)
    """
    phone_clean = phone_number.strip().replace(" ", "").replace("-", "")
    if len(phone_clean) != 11 or not (phone_clean.startswith("010") or phone_clean.startswith("011") or phone_clean.startswith("012") or phone_clean.startswith("015")):
        return False, "رقم الموبايل غير صحيح! يجب أن يتكون من 11 رقماً ويبدأ بـ (010 أو 011 أو 012 أو 015)", None
        
    if amount < min_amount:
        return False, f"الحد الأدنى للسحب هو {min_amount} جنيه", None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, "المستخدم غير موجود", None
            
        current_balance = row["balance"]
        if current_balance < amount:
            return False, f"رصيدك الحالي ({current_balance:.2f} ج) غير كافٍ لسحب ({amount:.2f} ج)", None
            
        # تحقق إذا كان لديه طلب قيد المراجعة بالفعل
        cursor.execute("SELECT id FROM withdrawals WHERE telegram_id = ? AND status = 'pending'", (telegram_id,))
        if cursor.fetchone():
            return False, "لديك طلب سحب سابق ما زال قيد المراجعة، يرجى الانتظار حتى تنفيذه", None
            
        new_balance = round(current_balance - amount, 2)
        now = int(time.time())
        
        # خصم الرصيد
        cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, telegram_id))
        
        # إنشاء الطلب
        cursor.execute("""
        INSERT INTO withdrawals (telegram_id, provider, phone_number, amount, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """, (telegram_id, provider, phone_clean, amount, now))
        
        withdrawal_id = cursor.lastrowid
        conn.commit()
        
        return True, "تم إرسال طلب السحب بنجاح! سيتم تحويل المبلغ قريباً.", withdrawal_id

def get_user_withdrawals(telegram_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM withdrawals WHERE telegram_id = ? ORDER BY id DESC LIMIT 20
        """, (telegram_id,))
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
    """
    تحديث حالة الطلب (approved أو rejected).
    في حالة الرفض، يتم إرجاع المبلغ المحجوز إلى رصيد المستخدم تلقائياً.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,))
        row = cursor.fetchone()
        
        if not row:
            return False, None
            
        withdrawal = dict(row)
        if withdrawal["status"] != "pending":
            return False, withdrawal # تم التعامل معه مسبقاً
            
        now = int(time.time())
        
        if new_status == "rejected":
            # إرجاع المبلغ لرصيد المستخدم
            cursor.execute("""
            UPDATE users SET balance = balance + ? WHERE telegram_id = ?
            """, (withdrawal["amount"], withdrawal["telegram_id"]))
            
        cursor.execute("""
        UPDATE withdrawals SET status = ?, reviewed_at = ? WHERE id = ?
        """, (new_status, now, withdrawal_id))
        
        conn.commit()
        withdrawal["status"] = new_status
        return True, withdrawal

def get_system_stats() -> Dict[str, Any]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_users, SUM(balance) AS total_balance, SUM(total_earned) AS total_paid_out, SUM(total_ads_watched) AS total_ads FROM users")
        stats = dict(cursor.fetchone())
        
        cursor.execute("SELECT COUNT(*) AS pending_count FROM withdrawals WHERE status = 'pending'")
        stats["pending_withdrawals"] = cursor.fetchone()["pending_count"]
        return stats
