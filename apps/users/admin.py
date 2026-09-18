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

class UserAdmin(BaseUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'name', 'role', 'total_spent', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    inlines = [EnrollmentInline]
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('name',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('RyuClass Profile', {'fields': ('total_spent', 'is_affiliate')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'role', 'password'),
        }),
    )
    search_fields = ('email', 'name')
    filter_horizontal = ('groups', 'user_permissions')
    actions = ['send_broadcast_email_action']

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
        # Save user object
        super().save_model(request, obj, form, change)
        
        # When user's total_spent or other details are saved/modified, recalculate their lifetime unlocks
        AccessService.recalculate_lifetime_unlocks(obj.id)

admin.site.register(User, UserAdmin)
