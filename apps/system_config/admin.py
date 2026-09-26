from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import SystemSetting, LifetimeStudentImport, MigrationRequest

@admin.register(SystemSetting)
class SystemSettingAdmin(ModelAdmin):
    list_display = ('key_name', 'key_value')
    search_fields = ('key_name', 'key_value')


@admin.register(LifetimeStudentImport)
class LifetimeStudentImportAdmin(ModelAdmin):
    list_display = ('id', 'email', 'level', 'invite_code', 'is_registered_badge', 'registered_at', 'created_at')
    list_filter = ('level', 'is_registered', 'created_at')
    search_fields = ('email', 'invite_code')

    @display(description="ลงทะเบียนแล้ว", boolean=True)
    def is_registered_badge(self, obj):
        return obj.is_registered


@admin.register(MigrationRequest)
class MigrationRequestAdmin(ModelAdmin):
    list_display = ('id', 'email', 'tracking_code', 'level', 'status_badge', 'created_at', 'processed_at')
    list_filter = ('status', 'level', 'created_at')
    search_fields = ('email', 'tracking_code', 'admin_note')
    actions = ['approve_migration', 'reject_migration']

    @display(
        description="สถานะคำขอ",
        label={
            "approved": "success",
            "pending": "warning",
            "rejected": "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="✅ อนุมัติการย้ายระบบ (Approve Migration)")
    def approve_migration(self, request, queryset):
        updated = queryset.update(status='approved', processed_at=timezone.now(), processed_by=request.user.id)
        self.message_user(request, f"อนุมัติคำขอย้ายระบบเรียบร้อยแล้ว {updated} รายการ", messages.SUCCESS)

    @admin.action(description="❌ ปฏิเสธคำขอย้ายระบบ (Reject Migration)")
    def reject_migration(self, request, queryset):
        updated = queryset.update(status='rejected', processed_at=timezone.now(), processed_by=request.user.id)
        self.message_user(request, f"ปฏิเสธคำขอย้ายระบบ {updated} รายการ", messages.WARNING)
