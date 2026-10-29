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
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    subject = "ขอบคุณที่สมัครมาเรียนด้วยกันครับ - RyuClass"
    message = (
        "ขอบคุณที่สมัครมาเรียนด้วยกันครับ เชิญเข้ากลุ่มเพื่อรับลิ้งค์ Zoom เข้าเรียนสดครับ\n\n"
        "เชิญเข้ากลุ่ม RYU CLASS เพื่อรับลิ้งค์เรียนสดผ่านระบบ ZOOM ได้ที่ https://line.me/R/ti/g/VDRgkPXRM9\n\n"
        "ขั้นตอนการเรียนคลิปย้อนหลัง\n\n"
        "1 ไปที่ Google พิมพ์ค้าหาว่า Ryuclass\n\n"
        "2.ทำการเข้าสู่ระบบ กรณีมือถือ ให้กดสามขีดด้านบน\n\n"
        "3.เข้าเรียนคลิปตาม Step ได้เลยครับ\n\n"
        "แล้วก็ขอเชิญเข้ากลุ่มนักเรียนพี่ริว กลุ่มนี้มีไว้รับข้อมูลข่าวสาร และพูดคุยกับเพื่อนๆที่เป็นสมาชิกด้วยกันครับ\n\n"
        "คุณได้รับคำเชิญให้เข้าร่วมกลุ่ม \"นักเรียนพี่ริว\" โปรดแตะลิงก์ด้านล่างเพื่อเข้าร่วมโอเพนแชทนี้\n"
        "https://line.me/ti/g2/ZJVKFgNw1ciVAzbsh5hbzezyEZ3O4bXJ-sZlWQ?utm_source=invitation&utm_medium=link_copy&utm_campaign=default\n\n"
        "รหัสผ่าน 12123\n\n"
        "ยินดีต้อนรับครับ"
    )

    html_content = """
    <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1e293b;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #2563eb; margin: 0; font-size: 24px;">🇯🇵 ยินดีต้อนรับสู่ RyuClass</h1>
            <p style="color: #64748b; margin-top: 6px; font-size: 15px;">ขอบคุณที่สมัครมาเรียนด้วยกันครับ</p>
        </div>

        <div style="background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 6px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 8px 0; color: #1e40af; font-size: 16px;">🔴 เข้ากลุ่มรับลิงก์เรียนสด ZOOM</h3>
            <p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.5;">เชิญเข้ากลุ่ม <strong>RYU CLASS</strong> เพื่อรับลิ้งค์เรียนสดผ่านระบบ ZOOM ได้ที่ปุ่มด้านล่าง:</p>
            <a href="https://line.me/R/ti/g/VDRgkPXRM9" style="display: inline-block; background-color: #06c755; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-size: 14px;">👉 เข้าร่วมกลุ่ม LINE Zoom สด</a>
        </div>

        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 12px 0; color: #0f172a; font-size: 16px;">📖 ขั้นตอนการเรียนคลิปย้อนหลัง</h3>
            <ol style="margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.8; color: #334155;">
                <li>ไปที่ Google พิมพ์ค้นหาว่า <strong>Ryuclass</strong> (หรือเข้าที่ www.ryusosense.online)</li>
                <li>ทำการเข้าสู่ระบบ (กรณีมือถือ ให้กดสามขีดด้านบน)</li>
                <li>เข้าเรียนคลิปตาม Step ได้เลยครับ</li>
            </ol>
        </div>

        <div style="background-color: #fefce8; border-left: 4px solid #eab308; padding: 16px; border-radius: 6px; margin-bottom: 24px;">
            <h3 style="margin: 0 0 8px 0; color: #854d0e; font-size: 16px;">💬 เชิญเข้ากลุ่ม OpenChat "นักเรียนพี่ริว"</h3>
            <p style="margin: 0 0 12px 0; font-size: 14px; line-height: 1.5;">กลุ่มนี้มีไว้รับข้อมูลข่าวสาร และพูดคุยกับเพื่อนๆ ที่เป็นสมาชิกด้วยกันครับ</p>
            <div style="background-color: #ffffff; border: 1px dashed #cbd5e1; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; font-size: 14px;">
                🔑 <strong>รหัสผ่านเข้ากลุ่ม:</strong> <span style="background-color: #fef08a; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 16px; color: #713f12;">12123</span>
            </div>
            <a href="https://line.me/ti/g2/ZJVKFgNw1ciVAzbsh5hbzezyEZ3O4bXJ-sZlWQ?utm_source=invitation&utm_medium=link_copy&utm_campaign=default" style="display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; font-size: 14px;">👉 เข้าร่วม OpenChat นักเรียนพี่ริว</a>
        </div>

        <div style="text-align: center; border-top: 1px solid #e2e8f0; padding-top: 16px; font-size: 14px; color: #64748b;">
            <p style="margin: 0; font-weight: bold; color: #0f172a;">ยินดีต้อนรับครับ แล้วเจอกันในคลาสนะครับ! 🐾</p>
            <p style="margin: 4px 0 0 0; font-size: 12px;">พี่ริว - RyuClass</p>
        </div>
    </div>
    """

    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'support@chatbotth.me'
        mail = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=from_email,
            to=[user.email]
        )
        mail.attach_alternative(html_content, "text/html")
        mail.send(fail_silently=True)
    except Exception:
        pass

