from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import SupportTicket, ChatLog, ConversationSession

@admin.register(SupportTicket)
class SupportTicketAdmin(ModelAdmin):
    list_display = ('id', 'user_info', 'category', 'status_badge', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('user__email', 'category', 'message')
    actions = ['mark_as_resolved', 'mark_as_pending']

    @display(description="ผู้ส่งตั๋ว")
    def user_info(self, obj):
        return f"{obj.user.name or obj.user.email} ({obj.user.email})"

    @display(
        description="สถานะ",
        label={
            "resolved": "success",
            "pending": "warning",
            "open": "info",
            "closed": "secondary",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="✅ ทำเครื่องหมายว่าแก้ไขแล้ว (Mark as RESOLVED)")
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='resolved')
        self.message_user(request, f"อัปเดตสถานะเป็นแก้ไขแล้วเรียบร้อย {updated} รายการ", messages.SUCCESS)

    @admin.action(description="⏳ ทำเครื่องหมายว่ารอดำเนินการ (Mark as PENDING)")
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f"อัปเดตสถานะเป็นรอดำเนินการ {updated} รายการ", messages.WARNING)


@admin.register(ChatLog)
class ChatLogAdmin(ModelAdmin):
    list_display = ('id', 'session_id', 'user', 'triggered_action', 'model_used', 'tokens_used', 'created_at')
    list_filter = ('triggered_action', 'model_used', 'created_at')
    search_fields = ('session_id', 'user__email', 'user_message', 'ai_response')


@admin.register(ConversationSession)
class ConversationSessionAdmin(ModelAdmin):
    list_display = ('id', 'session_id', 'user', 'state', 'order_amount', 'created_at')
    list_filter = ('state', 'created_at')
    search_fields = ('session_id', 'user__email')
