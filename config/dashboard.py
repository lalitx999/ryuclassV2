from django.db.models import Sum, Count
from users.models import User
from courses.models import Course
from payments.models import Payment

def dashboard_callback(request, context):
    """
    Dashboard context callback for Unfold Admin.
    Provides summary statistics matching the original RyuClass admin dashboard.
    """
    total_students = User.objects.filter(role='student').count()
    total_courses = Course.objects.filter(is_active=True).count()
    pending_payments = Payment.objects.filter(status='pending').count()
    revenue_agg = Payment.objects.filter(status='approved').aggregate(total=Sum('amount'))
    total_revenue = revenue_agg['total'] or 0

    recent_payments = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:8]

    context.update({
        "kpi_total_students": f"{total_students:,}",
        "kpi_total_courses": f"{total_courses:,}",
        "kpi_pending_payments": f"{pending_payments:,}",
        "kpi_total_revenue": f"฿{total_revenue:,.0f}",
        "recent_payments": recent_payments,
    })
    return context
