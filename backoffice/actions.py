"""Explicit administrative operations; independent of Django ModelAdmin."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .views import staff, resolve, audit, CHANGE

ACTIONS = {
    'post': {'approve': ('อนุมัติโพสต์', 'moderation_status', 'APPROVED'), 'reject': ('ปฏิเสธโพสต์', 'moderation_status', 'REJECTED')},
    'comment': {'approve': ('อนุมัติความคิดเห็น', 'moderation_status', 'APPROVED'), 'reject': ('ปฏิเสธความคิดเห็น', 'moderation_status', 'REJECTED')},
    'supportticket': {'resolve': ('ปิดคำร้อง', 'status', 'resolved'), 'reopen': ('เปิดคำร้องอีกครั้ง', 'status', 'pending')},
    'migrationrequest': {'approve': ('อนุมัติคำขอย้ายระบบ', 'status', 'approved'), 'reject': ('ปฏิเสธคำขอย้ายระบบ', 'status', 'rejected')},
    'affiliatepayout': {'paid': ('บันทึกว่าโอนเงินแล้ว', 'status', 'PAID'), 'reject': ('ปฏิเสธคำขอถอน', 'status', 'REJECTED')},
    'enrollment': {'remind': ('ส่งอีเมลเตือนต่ออายุ', None, None)},
}

@staff
@require_POST
def perform(request, app, name, pk):
    model = resolve(request, app, name, 'change')
    action = ACTIONS.get(name, {}).get(request.POST.get('action'))
    if not action:
        from django.http import Http404
        raise Http404
    label, field, value = action
    if name == 'enrollment':
        from courses.emails import send_course_renewal_reminder_email
        obj = get_object_or_404(model, pk=pk)
        if obj.is_lifetime_video or not obj.video_expires_at:
            messages.error(request, 'ส่งไม่ได้: สิทธิ์ตลอดชีพหรือไม่มีวันหมดอายุ')
        elif send_course_renewal_reminder_email(obj):
            audit(request, obj, CHANGE, label)
            messages.success(request, 'ส่งอีเมลแล้ว')
        else:
            messages.error(request, 'ส่งอีเมลไม่สำเร็จ กรุณาตรวจสอบระบบอีเมล')
    else:
        with transaction.atomic():
            obj = get_object_or_404(model.objects.select_for_update(), pk=pk)
            if name == 'affiliatepayout' and obj.status in {'PAID', 'REJECTED'}:
                messages.warning(request, 'รายการนี้ดำเนินการแล้ว')
                return redirect('backoffice:detail', app, name, pk)
            setattr(obj, field, value)
            if name == 'affiliatepayout' and value == 'PAID':
                obj.paid_at = timezone.now()
            if name == 'migrationrequest':
                obj.processed_at = timezone.now()
                obj.processed_by = request.user.pk
            obj.save()
            audit(request, obj, CHANGE, label)
            messages.success(request, label + 'แล้ว')
    return redirect('backoffice:detail', app, name, pk)
