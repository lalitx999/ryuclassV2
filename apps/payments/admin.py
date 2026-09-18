from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import Payment, SlipBlacklistPattern, SlipVerificationLog
from courses.services import AccessService

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'status', 'course', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'submitted_at', 'reviewed_at')
    search_fields = ('user__email', 'user__name', 'course__title', 'trans_ref')
    readonly_fields = ('slip_preview', 'submitted_at', 'reviewed_at')
    actions = ['approve_payments', 'reject_payments']

    fieldsets = (
        (None, {'fields': ('user', 'course', 'amount', 'duration_days', 'level_access', 'is_zoom_included')}),
        ('Transaction details', {'fields': ('trans_ref', 'telegram_message_id', 'note')}),
        ('Review Status', {'fields': ('status', 'rejection_reason', 'reviewed_by', 'reviewed_at')}),
        ('Attachment', {'fields': ('slip_path', 'slip_preview')}),
    )

    def slip_preview(self, obj):
        if obj.slip_path:
            url = f"/storage/slips/{obj.slip_path}"
            return mark_safe(
                f'<div style="margin-bottom: 10px;">'
                f'  <img src="{url}" style="max-width: 400px; max-height: 500px; border: 2px solid #ccc; border-radius: 4px;" />'
                f'</div>'
                f'<a href="{url}" target="_blank" class="button" style="padding: 4px 8px; background: #245dd7; color: white; text-decoration: none; border-radius: 3px;">'
                f'  👁️ Open Slip in New Tab'
                f'</a>'
            )
        return "No slip image uploaded"
    slip_preview.short_description = "Slip Image Preview"

    @admin.action(description="✅ อนุมัติสิทธิ์การเรียน (Approve selected payments & activate enrollment)")
    def approve_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'approved':
                # Update status
                payment.status = 'approved'
                payment.reviewed_at = timezone.now()
                payment.reviewed_by = request.user
                payment.save()

                # Call AccessService to add payment amount and calculate lifetime unlocks
                AccessService.add_payment(payment.user.id, payment.amount)

                # Create or update Enrollment for this student and course
                enrollment, created = Enrollment.objects.get_or_create(
                    user=payment.user,
                    course=payment.course,
                    defaults={'is_active': True, 'status': 'ACTIVE'}
                )
                enrollment.is_active = True
                enrollment.status = 'ACTIVE'
                if payment.duration_days == 9999:
                    enrollment.is_lifetime_video = True
                else:
                    expiry = AccessService.calculate_expiry(payment.duration_days, payment.is_zoom_included)
                    enrollment.video_expires_at = expiry['video']
                    if expiry['zoom']:
                        enrollment.zoom_expires_at = expiry['zoom']
                enrollment.save()
                count += 1
        
        self.message_user(
            request, 
            f"อนุมัติสิทธิ์การเรียนเรียบร้อยแล้วจำนวน {count} รายการ (เปิดสิทธิ์การเรียนในระบบให้อัตโนมัติ)",
            messages.SUCCESS
        )

    @admin.action(description="❌ ปฏิเสธรายการชำระเงิน (Reject selected payments)")
    def reject_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'rejected':
                payment.status = 'rejected'
                payment.reviewed_at = timezone.now()
                payment.reviewed_by = request.user
                payment.save()
                count += 1
        
        self.message_user(
            request, 
            f"ปฏิเสธรายการชำระเงินเรียบร้อยแล้วจำนวน {count} รายการ",
            messages.WARNING
        )


    def save_model(self, request, obj, form, change):
        # Detect if status is changing to approved
        old_status = None
        if change:
            try:
                old_status = Payment.objects.get(pk=obj.pk).status
            except Payment.DoesNotExist:
                pass
        
        # Set reviewed by and at if updated
        if obj.status != 'pending' and (not change or old_status == 'pending'):
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user

        super().save_model(request, obj, form, change)

        # Trigger AccessService on manual approval
        if obj.status == 'approved' and (not change or old_status != 'approved'):
            AccessService.add_payment(obj.user.id, obj.amount)

@admin.register(SlipBlacklistPattern)
class SlipBlacklistPatternAdmin(admin.ModelAdmin):
    list_display = ('id', 'pattern', 'type', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('pattern', 'description')

@admin.register(SlipVerificationLog)
class SlipVerificationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'user', 'status', 'verified_amount', 'verified_bank', 'verified_at')
    list_filter = ('status', 'verified_bank', 'verified_at')
    search_fields = ('user__email', 'payment__id', 'verified_account')
