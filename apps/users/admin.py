from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from .models import User
from courses.models import Enrollment
from courses.services import AccessService

class EnrollmentInline(TabularInline):
    model = Enrollment
    extra = 1
    fields = ('course', 'status', 'is_active', 'is_lifetime_video', 'video_expires_at', 'zoom_expires_at')
    autocomplete_fields = ('course',)

@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    ordering = ('email',)
    list_display = ('email', 'name', 'role_badge', 'total_spent_display', 'is_staff', 'is_active_badge')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    inlines = [EnrollmentInline]
    
    fieldsets = (
        ("เข้าสู่ระบบ & บัญชี", {'fields': ('email', 'password')}),
        ("ข้อมูลส่วนตัว", {'fields': ('name', 'nickname', 'phone', 'telegram_chat_id')}),
        ("สิทธิ์ในระบบ", {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ("ข้อมูล RyuClass", {'fields': ('total_spent', 'is_affiliate', 'email_verified')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password'),
        }),
    )
    search_fields = ('email', 'name', 'phone')
    filter_horizontal = ('groups', 'user_permissions')
    actions = ['send_broadcast_email_action']

    @display(
        description="บทบาท",
        label={
            "admin": "danger",
            "student": "info",
        }
    )
    def role_badge(self, obj):
        labels = {"admin": "ผู้ดูแลระบบ (Admin)", "student": "นักเรียน (Student)"}
        return labels.get(obj.role, obj.role)

    @display(
        description="สถานะบัญชี",
        boolean=True,
    )
    def is_active_badge(self, obj):
        return obj.is_active

    @display(description="ยอดซื้อสะสม")
    def total_spent_display(self, obj):
        return f"฿{obj.total_spent:,.2f}"

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
