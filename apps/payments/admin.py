from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from django.utils import timezone
from datetime import timedelta
from .models import Payment, SlipBlacklistPattern, SlipVerificationLog
from courses.models import Enrollment
from courses.services import AccessService

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_info', 'amount_display', 'course', 'status_badge', 'is_renewal', 'submitted_at')
    list_filter = ('status', 'submitted_at', 'reviewed_at', 'level_access')
    search_fields = ('user__email', 'user__name', 'course__title', 'trans_ref')
    readonly_fields = ('slip_preview', 'submitted_at', 'reviewed_at')
    actions = ['approve_payments', 'reject_payments']

    fieldsets = (
        ("ข้อมูลผู้เรียน & คอร์ส", {'fields': ('user', 'course', 'amount', 'duration_days', 'level_access', 'is_zoom_included', 'is_renewal', 'discount_percent')}),
        ("รายละเอียดการโอนเงิน", {'fields': ('trans_ref', 'telegram_message_id', 'note')}),
        ("สถานะการตรวจสอบ", {'fields': ('status', 'rejection_reason', 'reviewed_by', 'reviewed_at')}),
        ("หลักฐานสลิป", {'fields': ('slip_path', 'slip_preview')}),
    )

    def user_info(self, obj):
        return f"{obj.user.name or obj.user.email} ({obj.user.email})"
    user_info.short_description = "ผู้ชำระเงิน"

    def amount_display(self, obj):
        return f"฿{obj.amount:,.2f}"
    amount_display.short_description = "ยอดชำระ"

    def status_badge(self, obj):
        labels = {
            "approved": "อนุมัติแล้ว",
            "pending": "รอตรวจสอบ",
            "rejected": "ปฏิเสธ",
        }
        return labels.get(obj.status, obj.status)
    status_badge.short_description = "สถานะ"

    def slip_preview(self, obj):
        if obj.slip_path:
            url = f"/storage/slips/{obj.slip_path}"
            return mark_safe(
                f'<div style="margin-bottom: 12px;">'
                f'  <img src="{url}" style="max-width: 450px; max-height: 550px; border: 1px solid #e5e7eb; border-radius: 8px; shadow: 0 1px 3px rgba(0,0,0,0.1);" />'
                f'</div>'
                f'<a href="{url}" target="_blank" style="display: inline-block; padding: 6px 12px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 500; font-size: 13px;">'
                f'  👁️ เปิดรูปสลิปในหน้าต่างใหม่'
                f'</a>'
            )
        return "ไม่มีไฟล์สลิปแนบ"
    slip_preview.short_description = "ตัวอย่างสลิปโอนเงิน"

    @admin.action(description="✅ อนุมัติสิทธิ์การเรียน (Approve selected payments & activate enrollment)")
    def approve_payments(self, request, queryset):
        count = 0
        for payment in queryset:
            if payment.status != 'approved':
                payment.status = 'approved'
                payment.reviewed_at = timezone.now()
                payment.reviewed_by = request.user
                payment.save()

                # Calculate lifetime unlocks and totals
                AccessService.add_payment(payment.user.id, payment.amount)

                # Grant or update Enrollment
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
                    if payment.is_renewal and enrollment.video_expires_at:
                        enrollment.video_expires_at = max(enrollment.video_expires_at, timezone.now().date()) + timedelta(days=payment.duration_days)
                    else:
                        expiry = AccessService.calculate_expiry(payment.duration_days, payment.is_zoom_included)
                        enrollment.video_expires_at = expiry['video']
                        if expiry['zoom']:
                            enrollment.zoom_expires_at = expiry['zoom']
                enrollment.save()
                count += 1
        
        self.message_user(
            request, 
            f"อนุมัติสิทธิ์การเรียนเรียบร้อยแล้วจำนวน {count} รายการ (เปิดสิทธิ์การเรียนให้อัตโนมัติ)",
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
        old_status = None
        if change:
            try:
                old_status = Payment.objects.get(pk=obj.pk).status
            except Payment.DoesNotExist:
                pass
        
        if obj.status != 'pending' and (not change or old_status == 'pending'):
            obj.reviewed_at = timezone.now()
            obj.reviewed_by = request.user

        super().save_model(request, obj, form, change)

        if obj.status == 'approved' and (not change or old_status != 'approved'):
            AccessService.add_payment(obj.user.id, obj.amount)


@admin.register(SlipBlacklistPattern)
class SlipBlacklistPatternAdmin(admin.ModelAdmin):
    list_display = ('id', 'pattern', 'type', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('pattern', 'description')


@admin.register(SlipVerificationLog)
class SlipVerificationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'user', 'status_badge', 'verified_amount', 'verified_bank', 'verified_at')
    list_filter = ('status', 'verified_bank', 'verified_at')
    search_fields = ('user__email', 'payment__id', 'verified_account')

    def status_badge(self, obj):
        return obj.status
    status_badge.short_description = "สถานะตรวจสลิป"
