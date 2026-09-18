import os
import requests

def send_telegram_message(text: str) -> bool:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    admin_ids = os.getenv('TELEGRAM_ADMIN_CHAT_ID')
    if not token or not admin_ids:
        return False
    
    success = True
    for chat_id in admin_ids.split(','):
        chat_id = chat_id.strip()
        if not chat_id:
            continue
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            res = requests.post(url, json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }, timeout=10)
            if not res.json().get('ok'):
                success = False
        except Exception:
            success = False
    return success

def notify_admin_new_order(payment_id: int, student_name: str, student_email: str, course_name: str, amount: float) -> bool:
    text = (
        f"🛒 <b>คำสั่งซื้อใหม่!</b>\n\n"
        f"📋 รายการโอน #<b>{payment_id}</b>\n"
        f"👤 ผู้เรียน: <b>{student_name}</b>\n"
        f"📧 อีเมล: <code>{student_email}</code>\n"
        f"📚 คอร์ส: <b>{course_name}</b>\n"
        f"💰 ยอดโอน: <b>฿{amount:,.2f}</b>\n\n"
        f"🔗 ตรวจสอบที่: http://localhost:8000/admin/payments/payment/"
    )
    return send_telegram_message(text)
