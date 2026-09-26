from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from courses.models import Enrollment
from courses.services import AccessService

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    fields = ('course', 'status', 'is_active', 'is_lifetime_video', 'video_expires_at', 'zoom_expires_at')
    autocomplete_fields = ('course',)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'name', 'role_badge', 'total_spent_display', 'lifetime_tier_badge', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    inlines = [EnrollmentInline]
    readonly_fields = ('lifetime_progress_summary',)
    
    fieldsets = (
        ("เข้าสู่ระบบ & บัญชี", {'fields': ('email', 'password')}),
        ("ข้อมูลส่วนตัว", {'fields': ('name', 'nickname', 'phone', 'telegram_chat_id')}),
        ("สิทธิ์ในระบบ", {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ("ข้อมูล RyuClass & ระดับสะสม", {'fields': ('total_spent', 'lifetime_progress_summary', 'is_affiliate', 'email_verified')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password'),
        }),
    )
    search_fields = ('email', 'name', 'phone')
    actions = ['send_broadcast_email_action']

    def role_badge(self, obj):
        labels = {"admin": "ผู้ดูแลระบบ (Admin)", "student": "นักเรียน (Student)"}
        return labels.get(obj.role, obj.role)
    role_badge.short_description = "บทบาท"

    def total_spent_display(self, obj):
        return f"฿{obj.total_spent:,.2f}"
    total_spent_display.short_description = "ยอดซื้อสะสม"

    def lifetime_tier_badge(self, obj):
        from courses.services import AccessService
        from django.utils.html import format_html
        info = AccessService.get_tier_progress(obj.total_spent)
        if info['is_max_tier']:
            return format_html('<span style="background:#198754; color:#fff; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:11px;">💎 N1 Lifetime</span>')
        if info['current_level']:
            return format_html('<span style="background:#0d6efd; color:#fff; padding:3px 8px; border-radius:10px; font-size:11px;">⭐ {} (ขาด ฿{:,.0f})</span>', info['current_level'], float(info['remaining_amount']))
        return format_html('<span style="background:#6c757d; color:#fff; padding:3px 8px; border-radius:10px; font-size:11px;">เริ่มต้น (ขาด ฿{:,.0f})</span>', float(info['remaining_amount']))
    lifetime_tier_badge.short_description = "ระดับสะสม Lifetime"

    def lifetime_progress_summary(self, obj):
        from courses.services import AccessService
        from django.utils.html import format_html
        info = AccessService.get_tier_progress(obj.total_spent)
        
        if info['is_max_tier']:
            return format_html(
                '<div style="padding:12px; background:#d1e7dd; color:#0f5132; border-radius:8px; border:1px solid #badbcc;">'
                '<strong style="font-size:14px;">🏆 N1 Lifetime (สิทธิ์สูงสุด)</strong><br>'
                '<span style="font-size:12px;">{}</span>'
                '</div>',
                info['summary_text']
            )
        
        current = info['current_level'] or 'ยังไม่มีสิทธิ์'
        next_lvl = info['next_level']
        pct = info['progress_percent']
        rem = info['remaining_amount']
        
        return format_html(
            '<div style="padding:12px; background:#f8f9fa; border:1px solid #dee2e6; border-radius:8px; max-width:550px;">'
            '<div style="margin-bottom:6px; font-size:13px;">'
            '🏷️ <strong>ระดับปัจจุบัน:</strong> <span style="background:#0d6efd; color:#fff; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">{}</span> '
            '➔ <strong>เป้าหมายถัดไป:</strong> <span style="background:#ffc107; color:#000; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">{}</span>'
            '</div>'
            '<div style="margin-bottom:8px; font-size:12px; color:#495057;">'
            'ยอดสะสมปัจจุบัน: <strong>฿{:,.2f}</strong> / ฿{:,.2f} (ขาดอีก <strong style="color:#dc3545;">฿{:,.2f}</strong>)'
            '</div>'
            '<div style="width:100%; background:#e9ecef; height:12px; border-radius:6px; overflow:hidden;">'
            '<div style="width:{}%; background:linear-gradient(90deg, #0d6efd, #0dcaf0); height:100%;"></div>'
            '</div>'
            '<div style="font-size:11px; color:#6c757d; margin-top:4px; text-align:right;">ความคืบหน้าระดับนี้: {}%</div>'
            '</div>',
            current, next_lvl, float(obj.total_spent), float(info['next_threshold']), float(rem), pct, pct
        )
    lifetime_progress_summary.short_description = "สรุปความคืบหน้าสะสมสิทธิ์ Lifetime"

    @admin.action(description='📧 บรอดแคสต์ส่งอีเมลหาผู้ใช้ที่เลือก (Hostinger SMTP)')
    def send_broadcast_email_action(self, request, queryset):
        from django.core.mail import send_mail
        from django.conf import settings

        recipients = list(queryset.values_list('email', flat=True))
        if not recipients:
            self.message_user(request, "ไม่พบอีเมลผู้ใช้งานที่เลือก", level='error')
            return

        subject = "🔔 แจ้งเตือนข่าวสารและคอร์สเรียนจาก RyuClass"
        message = "สวัสดีครับนักเรียน RyuClass\n\nระบบขอแจ้งเตือนอัปเดตคอร์สเรียนและกิจกรรมภาษาญี่ปุ่นล่าสุด สามารถเข้าเรียนได้ทาง https://ryuclassv2.vercel.app\n\nขอให้สนุกกับการเรียนครับ!\nทีมงาน RyuClass"
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'RyuClass <support@chatbotth.me>')

        success_count = 0
        for email_addr in recipients:
            try:
                send_mail(subject, message, from_email, [email_addr], fail_silently=True)
                success_count += 1
            except Exception:
                pass

        self.message_user(request, f"ส่งอีเมลบรอดแคสต์สำเร็จแล้ว {success_count}/{len(recipients)} รายชื่อ")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AccessService.recalculate_lifetime_unlocks(obj.id)
