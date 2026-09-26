"""Permission-scoped dashboard queries. No demo metrics or visitor estimates."""
from datetime import timedelta
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from .registry import allowed


def dashboard_data(user):
    from users.models import User
    from courses.models import Course
    from payments.models import Payment
    from support.models import SupportTicket
    today = timezone.localdate()
    start = today - timedelta(days=29)
    data = {'cards': [], 'sales': None, 'revenue': None, 'recent': [], 'tickets': None,
            'course_sales': [], 'payment_counts': [], 'period_start': start, 'period_end': today}
    def url(model):
        return reverse('backoffice:list', args=[model._meta.app_label, model._meta.model_name])
    specs = [
        (Payment, 'สลิปรอตรวจ', {'status': 'pending'}, 'info', 'shopping-bag', '?status=pending'),
        (Course, 'คอร์สที่เปิดใช้งาน', {'is_active': True}, 'success', 'book-open', '?is_active=1'),
        (User, 'สมาชิกนักเรียน', {'role': 'student'}, 'warning', 'user-graduate', '?role=student'),
        (SupportTicket, 'คำร้องรอดำเนินการ', {'status': 'pending'}, 'danger', 'life-ring', '?status=pending'),
    ]
    for model, label, filters, color, icon, suffix in specs:
        if allowed(user, model):
            data['cards'].append(dict(label=label, value=model.objects.filter(**filters).count(),
                                      color=color, icon=icon, url=url(model) + suffix))
    if allowed(user, Payment):
        approved = Payment.objects.filter(status='approved')
        data['revenue'] = approved.aggregate(total=Sum('amount'))['total'] or 0
        # Use approval date, not upload date; NULL approval dates are not invented.
        daily = approved.filter(reviewed_at__date__gte=start, reviewed_at__date__lte=today).annotate(day=TruncDate('reviewed_at')).values('day').annotate(total=Sum('amount')).order_by('day')
        amounts = {row['day']: float(row['total']) for row in daily}
        days = [start + timedelta(days=i) for i in range(30)]
        data['sales'] = {'labels': [d.strftime('%d/%m') for d in days], 'amounts': [amounts.get(d, 0) for d in days]}
        data['period_revenue'] = sum(data['sales']['amounts'])
        data['recent'] = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:6]
        data['course_sales'] = list(approved.values('course_id', 'course__title').annotate(total=Sum('amount')).order_by('-total')[:5])
        data['payment_counts'] = [{'label': label, 'count': Payment.objects.filter(status=status).count(), 'url': url(Payment) + '?status=' + status} for status, label in [('pending', 'รอตรวจ'), ('approved', 'อนุมัติแล้ว'), ('rejected', 'ปฏิเสธ')]]
    if allowed(user, SupportTicket):
        data['tickets'] = SupportTicket.objects.filter(status='pending').select_related('user').order_by('-created_at')[:5]
    return data
