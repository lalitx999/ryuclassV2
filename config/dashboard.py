from django.db.models import Sum
from users.models import User
from courses.models import Course
from payments.models import Payment

def dashboard_callback(request, context):
    """
    Dashboard context callback for Unfold Admin.
    Provides summary statistics matching the original RyuClass admin dashboard.
    Safe fallback wrapped in try-except block to prevent 500/502 errors.
    """
    try:
        total_students = User.objects.filter(role='student').count()
        total_courses = Course.objects.filter(is_active=True).count()
        pending_payments = Payment.objects.filter(status='pending').count()
        revenue_agg = Payment.objects.filter(status='approved').aggregate(total=Sum('amount'))
        total_revenue = revenue_agg['total'] or 0
        recent_payments = list(Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:8])
    except Exception:
        total_students = 0
        total_courses = 0
        pending_payments = 0
        total_revenue = 0
        recent_payments = []

    context.update({
        "kpi_total_students": f"{total_students:,}",
        "kpi_total_courses": f"{total_courses:,}",
        "kpi_pending_payments": f"{pending_payments:,}",
        "kpi_total_revenue": f"฿{total_revenue:,.0f}",
        "recent_payments": recent_payments,
    })
    return context
