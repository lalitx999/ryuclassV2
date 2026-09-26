from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import AffiliateProfile, AffiliateClick, AffiliateCommission, AffiliateCouponLog, AffiliatePayout

@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(ModelAdmin):
    list_display = ('id', 'ref_code', 'user', 'commission_rate', 'holding_amount', 'ready_amount', 'withdrawn_amount', 'status_badge')
    list_filter = ('status', 'created_at')
    search_fields = ('ref_code', 'user__email', 'user__name')

    @display(
        description="สถานะ",
        label={
            "ACTIVE": "success",
            "SUSPENDED": "danger",
            "PENDING": "warning",
        }
    )
    def status_badge(self, obj):
        return obj.status


@admin.register(AffiliateClick)
class AffiliateClickAdmin(ModelAdmin):
    list_display = ('id', 'affiliate_profile', 'ip_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('affiliate_profile__ref_code', 'ip_address')


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(ModelAdmin):
    list_display = ('id', 'affiliate_profile', 'order_amount', 'commission_amount', 'status_badge', 'hold_until', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('affiliate_profile__ref_code', 'buyer_user__email')

    @display(
        description="สถานะค่าคอม",
        label={
            "APPROVED": "success",
            "READY": "info",
            "HOLDING": "warning",
            "REJECTED": "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status


@admin.register(AffiliateCouponLog)
class AffiliateCouponLogAdmin(ModelAdmin):
    list_display = ('id', 'ref_code', 'referred_user', 'discounted_amount', 'accepted_at')
    search_fields = ('ref_code', 'referred_user__email')


@admin.register(AffiliatePayout)
class AffiliatePayoutAdmin(ModelAdmin):
    list_display = ('id', 'user', 'amount_display', 'bank_name', 'bank_account', 'account_name', 'status_badge', 'requested_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('user__email', 'account_name', 'bank_account')
    actions = ['mark_as_paid', 'mark_as_rejected']

    @display(description="ยอดถอน")
    def amount_display(self, obj):
        return f"฿{obj.amount:,.2f}"

    @display(
        description="สถานะจ่ายเงิน",
        label={
            "PAID": "success",
            "REQUESTED": "warning",
            "REJECTED": "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="💰 อนุมัติการโอนเงิน (Mark as PAID)")
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='PAID', paid_at=timezone.now())
        self.message_user(request, f"อนุมัติจ่ายเงินเรียบร้อยแล้ว {updated} รายการ", messages.SUCCESS)

    @admin.action(description="❌ ปฏิเสธรายการถอน (Mark as REJECTED)")
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        self.message_user(request, f"ปฏิเสธรายการถอนเงินเรียบร้อยแล้ว {updated} รายการ", messages.WARNING)
