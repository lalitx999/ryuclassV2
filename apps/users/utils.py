import os
import requests
from django.utils import timezone

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

def send_telegram_photo(photo_path: str, caption: str) -> bool:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    admin_ids = os.getenv('TELEGRAM_ADMIN_CHAT_ID')
    if not token or not admin_ids:
        return False
    
    if not photo_path or not os.path.exists(photo_path):
        return send_telegram_message(caption)
    
    success = True
    for chat_id in admin_ids.split(','):
        chat_id = chat_id.strip()
        if not chat_id:
            continue
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo_path, 'rb') as photo_file:
                res = requests.post(url, data={
                    'chat_id': chat_id,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }, files={'photo': photo_file}, timeout=15)
                if not res.json().get('ok'):
                    success = False
        except Exception:
            success = False
    return success

def notify_admin_new_order(
    payment_id: int,
    student_name: str,
    student_email: str,
    course_name: str,
    amount: float,
    phone: str = '',
    level: str = '',
    duration: int = 30,
    slip_file_path: str = None,
    trans_ref: str = '',
    is_auto_approved: bool = False
) -> bool:
    site_url = os.getenv('SITE_URL', 'http://localhost:8000').rstrip('/')
    admin_link = f"{site_url}/admin/payments/payment/"
    
    status_header = "💰 <b>AUTO-APPROVED NEW REGISTRATION</b>" if is_auto_approved else "🛒 <b>คำสั่งซื้อใหม่ / NEW REGISTRATION</b>"
    
    now_str = timezone.now().strftime("%d/%m/%Y %H:%M")
    
    lines = [
        status_header,
        f"👤 <b>{student_name}</b>",
        f"📧 <code>{student_email}</code>",
    ]
    if phone:
        lines.append(f"📞 <code>{phone}</code>")
    if level:
        lines.append(f"📚 Level: <b>{level}</b> ({course_name})")
    else:
        lines.append(f"📚 Course: <b>{course_name}</b>")
    
    if duration:
        lines.append(f"⌛ Duration: <b>{duration} days</b>")
    
    lines.append(f"💰 Amount: <b>฿{amount:,.2f}</b>")
    
    if trans_ref:
        lines.append(f"🔑 Ref: <code>{trans_ref}</code>")
    else:
        lines.append(f"📋 Ref / Payment ID: #<b>{payment_id}</b>")
        
    lines.append(f"⏰ {now_str}")
    lines.append(f"\n🔗 <a href='{admin_link}'>ตรวจสอบสลิปใน Admin</a>")
    
    caption = "\n".join(lines)
    
    return send_telegram_photo(slip_file_path, caption)

def send_welcome_student_email(user):
    """Send welcome and instructions email to student upon registration or renewal."""
    from django.core.mail import send_mail
    from django.conf import settings

    subject = "ขอบคุณที่สมัครเรียนกับพี่ริวครับ"
    message = (
        "ขอบคุณที่สมัครเรียนกับพี่ริวครับ\n\n"
        "ขั้นตอนการเรียนคลิปย้อนหลัง\n\n"
        "1 ไปที่ Google พิมพ์ค้าหาว่า Ryuclass\n\n"
        "2.ทำการเข้าสู่ระบบ กรณีมือถือ ให้กดสามขีดด้านบน\n\n"
        "3.เข้าเรียนคลิปตาม Step ได้เลยครับ\n\n"
        "คุณได้รับคำเชิญให้เข้าร่วมกลุ่ม LINE \"นักเรียนพี่ริว\" โปรดแตะลิงก์ด้านล่างเพื่อเข้าร่วมโอเพนแชทนี้\n"
        "https://line.me/ti/g2/ZJVKFgNw1ciVAzbsh5hbzezyEZ3O4bXJ-sZlWQ?utm_source=invitation&utm_medium=link_copy&utm_campaign=default\n\n"
        "รหัสผ่าน 12123\n\n"
        "ยินดีต้อนรับคร๊าบ"
    )
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'support@chatbotth.me'
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            fail_silently=True
        )
    except Exception:
        pass

