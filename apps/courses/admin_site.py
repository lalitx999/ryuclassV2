from django.contrib import admin
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum
from courses.models import Course, Module, Lesson, Enrollment
from payments.models import Payment
from users.models import User

class RyuCustomAdminSite(admin.AdminSite):
    """
    Custom AdminSite for RyuClass Single-Page Management Dashboard (TailwindAdmin-1.0.0 + HTMX).
    Wraps ALL custom views with self.admin_view() to guarantee Django Admin authentication & permissions.
    """
    site_header = "RyuClass Admin Portal"
    site_title = "RyuClass Admin Dashboard"
    index_title = "แดชบอร์ดบริหารจัดการ RyuClass"

    def get_urls(self):
        """
        Register custom endpoints for HTMX Single-Page Management.
        All custom views are wrapped in self.admin_view() for security.
        """
        urls = super().get_urls()
        custom_urls = [
            # 1. Main Single-Page Management Feed Dashboard
            path('', self.admin_view(self.dashboard_view), name='index'),

            # 2. HTMX Endpoints for Courses (Single-Page Feed Swapping)
            path('htmx/course/<int:course_id>/card/', self.admin_view(self.course_card_view), name='htmx_course_card'),
            path('htmx/course/<int:course_id>/edit/', self.admin_view(self.course_edit_form_view), name='htmx_course_edit'),
            path('htmx/course/<int:course_id>/save/', self.admin_view(self.course_save_view), name='htmx_course_save'),
            path('htmx/course/create/', self.admin_view(self.course_create_view), name='htmx_course_create'),
            path('htmx/course/<int:course_id>/delete/', self.admin_view(self.course_delete_view), name='htmx_course_delete'),

            # 3. HTMX Endpoints for Lessons
            path('htmx/lesson/<int:lesson_id>/edit/', self.admin_view(self.lesson_edit_view), name='htmx_lesson_edit'),
            path('htmx/lesson/<int:lesson_id>/save/', self.admin_view(self.lesson_save_view), name='htmx_lesson_save'),
            path('htmx/lesson/<int:lesson_id>/delete/', self.admin_view(self.lesson_delete_view), name='htmx_lesson_delete'),
            path('htmx/course/<int:course_id>/lesson/create/', self.admin_view(self.lesson_create_view), name='htmx_lesson_create'),
        ]
        return custom_urls + urls

    # ------------------------------------------------------------------
    # Custom View Implementations (Protected by self.admin_view)
    # ------------------------------------------------------------------

    def dashboard_view(self, request):
        """
        Main Single-Page Management Feed.
        Displays KPI metrics, Recent Payment Slips Table, Recent Students, and Course Management Feed.
        """
        courses = Course.objects.prefetch_related('modules__lessons').all().order_by('sort_order', '-id')
        total_students = User.objects.filter(role='student').count()
        total_courses = Course.objects.filter(is_active=True).count()
        pending_payments = Payment.objects.filter(status='pending').count()
        
        revenue_agg = Payment.objects.filter(status='approved').aggregate(total=Sum('amount'))
        total_revenue = revenue_agg['total'] or 0

        recent_payments = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:6]
        recent_students = User.objects.filter(role='student').order_by('-created_at')[:5]

        context = {
            **self.each_context(request),
            'courses': courses,
            'total_students': f"{total_students:,}",
            'total_courses': f"{total_courses:,}",
            'pending_payments': f"{pending_payments:,}",
            'total_revenue': f"฿{total_revenue:,.0f}",
            'recent_payments': recent_payments,
            'recent_students': recent_students,
            'title': 'แดชบอร์ดผู้ดูแลระบบ RyuClass (Single-Page Dashboard)',
        }
        return render(request, 'custom_admin/dashboard.html', context)

    def course_card_view(self, request, course_id):
        """Render single course card HTML partial."""
        course = get_object_or_404(Course, pk=course_id)
        return render(request, 'custom_admin/partials/course_card.html', {'course': course})

    def course_edit_form_view(self, request, course_id):
        """Render inline course edit form HTML partial."""
        course = get_object_or_404(Course, pk=course_id)
        return render(request, 'custom_admin/partials/course_form.html', {'course': course})

    def course_save_view(self, request, course_id):
        """Save course edits via HTMX POST and return updated card partial."""
        if request.method == 'POST':
            course = get_object_or_404(Course, pk=course_id)
            course.title = request.POST.get('title', course.title)
            try:
                course.price = float(request.POST.get('price', course.price))
            except ValueError:
                pass
            course.is_active = request.POST.get('is_active') == 'on'
            course.save()
            return render(request, 'custom_admin/partials/course_card.html', {'course': course})
        return HttpResponse(status=400)

    def course_create_view(self, request):
        """Create a new course via HTMX and append new card to feed."""
        if request.method == 'POST':
            title = request.POST.get('title', 'คอร์สเรียนภาษาญี่ปุ่นใหม่')
            try:
                price = float(request.POST.get('price', 0))
            except ValueError:
                price = 0
            course = Course.objects.create(title=title, price=price, is_active=True)
            return render(request, 'custom_admin/partials/course_card.html', {'course': course})
        return HttpResponse(status=400)

    def course_delete_view(self, request, course_id):
        """Delete course via HTMX and return 200 OK empty response so HTMX removes element."""
        if request.method in ['POST', 'DELETE']:
            course = get_object_or_404(Course, pk=course_id)
            course.delete()
            return HttpResponse("")
        return HttpResponse(status=400)

    def lesson_edit_view(self, request, lesson_id):
        """Render inline lesson edit form partial."""
        lesson = get_object_or_404(Lesson, pk=lesson_id)
        return render(request, 'custom_admin/partials/lesson_form.html', {'lesson': lesson})

    def lesson_save_view(self, request, lesson_id):
        """Save lesson edits via HTMX POST and return updated lesson item partial."""
        if request.method == 'POST':
            lesson = get_object_or_404(Lesson, pk=lesson_id)
            lesson.title = request.POST.get('title', lesson.title)
            lesson.is_free = request.POST.get('is_free') == 'on'
            lesson.save()
            return render(request, 'custom_admin/partials/lesson_item.html', {'lesson': lesson})
        return HttpResponse(status=400)

    def lesson_delete_view(self, request, lesson_id):
        """Delete lesson via HTMX and return empty response."""
        if request.method in ['POST', 'DELETE']:
            lesson = get_object_or_404(Lesson, pk=lesson_id)
            lesson.delete()
            return HttpResponse("")
        return HttpResponse(status=400)

    def lesson_create_view(self, request, course_id):
        """Create a new lesson under a course via HTMX."""
        if request.method == 'POST':
            course = get_object_or_404(Course, pk=course_id)
            title = request.POST.get('title', 'บทเรียนใหม่')
            lesson = Lesson.objects.create(course=course, title=title, is_active=True)
            return render(request, 'custom_admin/partials/lesson_item.html', {'lesson': lesson})
        return HttpResponse(status=400)

# Instantiate Custom Admin Site
custom_admin_site = RyuCustomAdminSite(name='custom_admin')
