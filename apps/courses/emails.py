import logging
from datetime import date
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import Enrollment

logger = logging.getLogger(__name__)

def send_course_renewal_reminder_email(enrollment: Enrollment, days_remaining: int = None) -> bool:
    """
    Sends a beautifully formatted course membership renewal reminder email to a student.
    """
    if not enrollment.user or not enrollment.user.email:
        logger.warning(f"Enrollment {enrollment.id} has no valid user or email.")
        return False

    user = enrollment.user
    course = enrollment.course
    user_name = getattr(user, 'name', '') or getattr(user, 'username', '') or user.email.split('@')[0]
    expiry_date_str = enrollment.video_expires_at.strftime('%d/%m/%Y') if enrollment.video_expires_at else 'ไม่ระบุ'
    
    # Calculate days if not explicitly provided
    if days_remaining is None and enrollment.video_expires_at:
        today = date.today()
        days_remaining = (enrollment.video_expires_at - today).days

    # Determine status banner text and colors
    if days_remaining is not None and days_remaining < 0:
        headline = "⏰ สิทธิ์เข้าเรียนคอร์สของคุณหมดอายุแล้ว"
        status_sub = f"สิทธิ์เข้าเรียนคอร์ส <strong>{course.title}</strong> หมดอายุเมื่อวันที่ <strong>{expiry_date_str}</strong>"
        badge_color = "#ef4444"  # Red
        badge_text = "EXPIRED / หมดอายุ"
    elif days_remaining == 0:
        headline = "⚠️ สิทธิ์เข้าเรียนคอร์สของคุณหมดอายุวันนี้!"
        status_sub = f"สิทธิ์เข้าเรียนคอร์ส <strong>{course.title}</strong> จะหมดอายุในวันนี้ (<strong>{expiry_date_str}</strong>)"
        badge_color = "#f59e0b"  # Amber
        badge_text = "EXPIRES TODAY / หมดอายุวันนี้"
    else:
        days_str = f"{days_remaining} วัน" if days_remaining is not None else ""
        headline = f"⏳ แจ้งเตือน: สิทธิ์เรียนคอร์สของคุณจะหมดอายุในอีก {days_str}"
        status_sub = f"สิทธิ์เข้าเรียนคอร์ส <strong>{course.title}</strong> กำลังจะหมดอายุในวันที่ <strong>{expiry_date_str}</strong> (เหลือเวลาอีก {days_str})"
        badge_color = "#3b82f6"  # Blue
        badge_text = f"REMAINING {days_str} / เหลือเวลาอีก {days_str}"

    subject = f"[RyuClass] แจ้งเตือนต่ออายุคอร์สเรียน: {course.title}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
    </head>
    <body style="margin:0; padding:0; background-color:#0f172a; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color:#e2e8f0;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px; margin:30px auto; background-color:#1e293b; border-radius:16px; overflow:hidden; border:1px solid #334155; box-shadow:0 10px 25px -5px rgba(0, 0, 0, 0.5);">
            <!-- Header Banner -->
            <tr>
                <td style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 32px 24px; text-align: center;">
                    <h1 style="color:#ffffff; margin:0; font-size:26px; font-weight:800; letter-spacing: -0.5px;">RyuClass 日本語</h1>
                    <p style="color:#e0e7ff; margin:6px 0 0 0; font-size:14px; opacity:0.9;">โรงเรียนสอนภาษาญี่ปุ่นออนไลน์ RyuClass</p>
                </td>
            </tr>

            <!-- Status Badge -->
            <tr>
                <td style="padding: 24px 32px 8px 32px; text-align: center;">
                    <span style="display:inline-block; background-color:{badge_color}; color:#ffffff; font-size:12px; font-weight:700; padding:6px 16px; border-radius:9999px; text-transform:uppercase; letter-spacing:1px;">
                        {badge_text}
                    </span>
                </td>
            </tr>

            <!-- Body Content -->
            <tr>
                <td style="padding: 16px 32px 32px 32px;">
                    <h2 style="color:#f8fafc; font-size:20px; margin-top:0; margin-bottom:16px;">{headline}</h2>
                    <p style="color:#cbd5e1; font-size:15px; line-height:1.6; margin-bottom:16px;">
                        สวัสดีคุณ <strong>{user_name}</strong>,
                    </p>
                    <p style="color:#cbd5e1; font-size:15px; line-height:1.6; margin-bottom:24px;">
                        {status_sub} เพื่อการเรียนรู้ภาษาญี่ปุ่นอย่างต่อเนื่องและไม่ขาดช่วง ขอแนะนำให้ดำเนินการต่ออายุคอร์สเรียนของคุณ
                    </p>

                    <!-- Details Box -->
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0f172a; border-radius:12px; padding:20px; border:1px solid #334155; margin-bottom:28px;">
                        <tr>
                            <td style="color:#94a3b8; font-size:13px; padding-bottom:8px;">ชื่อคอร์สเรียน:</td>
                            <td style="color:#f8fafc; font-size:14px; font-weight:600; padding-bottom:8px; text-align:right;">{course.title}</td>
                        </tr>
                        <tr>
                            <td style="color:#94a3b8; font-size:13px; padding-bottom:8px;">อีเมลผู้ใช้งาน:</td>
                            <td style="color:#38bdf8; font-size:14px; font-weight:600; padding-bottom:8px; text-align:right;">{user.email}</td>
                        </tr>
                        <tr>
                            <td style="color:#94a3b8; font-size:13px;">วันหมดอายุสิทธิ์:</td>
                            <td style="color:#f43f5e; font-size:14px; font-weight:700; text-align:right;">{expiry_date_str}</td>
                        </tr>
                    </table>

                    <!-- Call To Action -->
                    <div style="text-align: center; margin-bottom: 24px;">
                        <a href="https://ryuclassv2.vercel.app/courses" target="_blank" style="display:inline-block; background:linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color:#ffffff; text-decoration:none; font-weight:700; font-size:16px; padding:14px 32px; border-radius:10px; box-shadow:0 4px 14px 0 rgba(99, 102, 241, 0.39);">
                            🔗 เข้าสู่ระบบเพื่อต่ออายุคอร์สเรียน
                        </a>
                    </div>

                    <p style="color:#94a3b8; font-size:13px; line-height:1.5; text-align:center;">
                        หากมีข้อสงสัยหรือต้องการสอบถามเพิ่มเติมเกี่ยวกับการต่ออายุ สามารถติดต่อทีมงาน RyuClass ได้ตลอดเวลาครับ
                    </p>
                </td>
            </tr>

            <!-- Footer -->
            <tr>
                <td style="background-color:#0f172a; padding:20px 32px; border-top:1px solid #334155; text-align:center;">
                    <p style="color:#64748b; font-size:12px; margin:0;">
                        © RyuClass Online Japanese School. All rights reserved.<br>
                        อีเมลนี้ส่งจากระบบอัตโนมัติ (support@chatbotth.me)
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    plain_text_status = status_sub.replace('<strong>', '').replace('</strong>', '')
    text_content = f"""
    [RyuClass] แจ้งเตือนต่ออายุคอร์สเรียน: {course.title}
    --------------------------------------------------
    สวัสดีคุณ {user_name},

    {plain_text_status}
    
    รายละเอียดคอร์ส: {course.title}
    อีเมล: {user.email}
    วันหมดอายุ: {expiry_date_str}

    ต่ออายุคอร์สเรียนได้ที่: https://ryuclassv2.vercel.app/courses

    ขอบคุณครับ,
    ทีมงาน RyuClass
    """

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'RyuClass <support@chatbotth.me>')

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Renewal reminder email sent successfully to {user.email} for enrollment ID {enrollment.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send renewal reminder email to {user.email}: {e}")
        return False
