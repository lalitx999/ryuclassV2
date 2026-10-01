import os
import csv
import time
from decimal import Decimal
from datetime import timedelta
from urllib.parse import quote

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, parsers
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.http import HttpResponse
from django.conf import settings

from users.models import User
from courses.models import Course, Module, Lesson, Enrollment
from courses.services import AccessService
from courses.utils import save_pdf_file
from payments.models import Payment, SlipVerificationLog
from payments.utils import approve_payment_transaction
from support.models import SupportTicket

def is_staff_member(user):
    return user and user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'role', '') == 'admin')

class AdminAuthMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        return Response({
            'id': request.user.id,
            'name': request.user.name or request.user.email,
            'email': request.user.email,
            'role': request.user.role,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        })

class AdminDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.localdate()
        start_date = today - timedelta(days=29)

        pending_payments_count = Payment.objects.filter(status='pending').count()
        active_courses_count = Course.objects.filter(is_active=True).count()
        total_students_count = User.objects.filter(role='student').count()
        pending_tickets_count = SupportTicket.objects.filter(status='pending').count()

        approved_payments = Payment.objects.filter(status='approved')
        total_revenue = approved_payments.aggregate(total=Sum('amount'))['total'] or 0

        # Sales last 30 days
        daily_sales_qs = approved_payments.filter(
            reviewed_at__date__gte=start_date,
            reviewed_at__date__lte=today
        ).annotate(day=TruncDate('reviewed_at')).values('day').annotate(total=Sum('amount')).order_by('day')

        amounts_dict = {row['day']: float(row['total']) for row in daily_sales_qs}
        days_list = [start_date + timedelta(days=i) for i in range(30)]
        chart_labels = [d.strftime('%d/%m') for d in days_list]
        chart_amounts = [amounts_dict.get(d, 0.0) for d in days_list]

        # Top 5 courses by revenue
        top_courses = list(
            approved_payments.values('course_id', 'course__title')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:5]
        )
        for c in top_courses:
            c['total'] = float(c['total'])

        # Recent 6 payments
        recent_payments_qs = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:6]
        recent_payments = []
        for p in recent_payments_qs:
            recent_payments.append({
                'id': p.id,
                'user_name': p.user.name or p.user.email,
                'user_email': p.user.email,
                'course_title': p.course.title,
                'amount': float(p.amount),
                'status': p.status,
                'submitted_at': p.submitted_at.strftime('%d/%m/%Y %H:%M') if p.submitted_at else '-'
            })

        return Response({
            'cards': {
                'pending_payments': pending_payments_count,
                'active_courses': active_courses_count,
                'total_students': total_students_count,
                'pending_tickets': pending_tickets_count,
                'total_revenue': float(total_revenue),
            },
            'sales_chart': {
                'labels': chart_labels,
                'amounts': chart_amounts,
                'period_revenue': sum(chart_amounts)
            },
            'top_courses': top_courses,
            'recent_payments': recent_payments,
        })

class AdminPaymentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.GET.get('status', '').strip()
        search_q = request.GET.get('q', '').strip()
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        queryset = Payment.objects.select_related('user', 'course').order_by('-submitted_at')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search_q:
            queryset = queryset.filter(
                Q(user__email__icontains=search_q) |
                Q(user__name__icontains=search_q) |
                Q(course__title__icontains=search_q) |
                Q(trans_ref__icontains=search_q)
            )

        total_count = queryset.count()
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        page_items = queryset[start_idx:end_idx]

        results = []
        slips_dir = getattr(settings, 'SLIPS_STORAGE_DIR', '')
        for p in page_items:
            slip_url = None
            if p.slip_path:
                slip_url = f"/storage/slips/{quote(p.slip_path)}"
            results.append({
                'id': p.id,
                'user_id': p.user.id,
                'user_name': p.user.name or p.user.email,
                'user_email': p.user.email,
                'user_phone': getattr(p.user, 'phone', '') or '-',
                'course_id': p.course.id,
                'course_title': p.course.title,
                'amount': float(p.amount),
                'duration_days': p.duration_days,
                'level_access': p.level_access,
                'slip_path': p.slip_path,
                'slip_url': slip_url,
                'status': p.status,
                'rejection_reason': p.rejection_reason or '',
                'submitted_at': p.submitted_at.strftime('%d/%m/%Y %H:%M') if p.submitted_at else '-',
                'reviewed_at': p.reviewed_at.strftime('%d/%m/%Y %H:%M') if p.reviewed_at else None,
            })

        return Response({
            'total': total_count,
            'page': page_num,
            'page_size': page_size,
            'results': results
        })

class AdminPaymentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        try:
            payment = Payment.objects.select_related('user', 'course').get(pk=pk)
        except Payment.DoesNotExist:
            return Response({'error': 'ไม่พบรายการชำระเงินนี้'}, status=status.HTTP_404_NOT_FOUND)

        easyslip_log = SlipVerificationLog.objects.filter(payment=payment).order_by('-verified_at').first()
        easyslip_data = None
        if easyslip_log:
            easyslip_data = {
                'id': easyslip_log.id,
                'status': easyslip_log.status,
                'status_display': easyslip_log.get_status_display(),
                'verified_amount': float(easyslip_log.verified_amount) if easyslip_log.verified_amount else None,
                'verified_bank': easyslip_log.verified_bank,
                'verified_account': easyslip_log.verified_account,
                'error_message': easyslip_log.error_message,
                'verified_at': easyslip_log.verified_at.strftime('%d/%m/%Y %H:%M') if easyslip_log.verified_at else None,
            }

        slip_url = f"/storage/slips/{quote(payment.slip_path)}" if payment.slip_path else None

        return Response({
            'id': payment.id,
            'user': {
                'id': payment.user.id,
                'name': payment.user.name or payment.user.email,
                'email': payment.user.email,
                'phone': getattr(payment.user, 'phone', ''),
                'total_spent': float(payment.user.total_spent),
            },
            'course': {
                'id': payment.course.id,
                'title': payment.course.title,
                'price': float(payment.course.price),
            },
            'amount': float(payment.amount),
            'duration_days': payment.duration_days,
            'level_access': payment.level_access,
            'is_zoom_included': payment.is_zoom_included,
            'slip_path': payment.slip_path,
            'slip_url': slip_url,
            'trans_ref': payment.trans_ref,
            'status': payment.status,
            'rejection_reason': payment.rejection_reason or '',
            'submitted_at': payment.submitted_at.strftime('%d/%m/%Y %H:%M') if payment.submitted_at else '-',
            'easyslip_log': easyslip_data,
        })

class AdminPaymentReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action') # 'approve' or 'reject'
        reason = str(request.data.get('reason', '')).strip()

        if action not in ('approve', 'reject'):
            return Response({'error': 'action ต้องเป็น approve หรือ reject เท่านั้น'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.select_for_update().get(pk=pk)
        except Payment.DoesNotExist:
            return Response({'error': 'ไม่พบรายการชำระเงินนี้'}, status=status.HTTP_404_NOT_FOUND)

        if payment.status != 'pending':
            return Response({'error': f'รายการนี้ผ่านการตรวจไปแล้ว (สถานะปัจจุบัน: {payment.status})'}, status=400)

        if action == 'reject' and not reason:
            return Response({'error': 'กรุณาระบุเหตุผลในการปฏิเสธสลิป'}, status=400)

        if action == 'approve':
            approve_payment_transaction(payment, reviewed_by=request.user)
        else:
            payment.status = 'rejected'
            payment.rejection_reason = reason[:255]
            payment.reviewed_by = request.user
            payment.reviewed_at = timezone.now()
            payment.save()

        return Response({
            'message': 'บันทึกผลการตรวจสอบสลิปเรียบร้อยแล้ว',
            'status': payment.status,
            'payment_id': payment.id
        })

class AdminCoursesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        
        courses = Course.objects.all().order_by('sort_order')
        results = []
        for c in courses:
            modules_qs = Module.objects.filter(course=c, is_active=True).order_by('sort_order')
            modules_list = []
            for m in modules_qs:
                lessons_qs = Lesson.objects.filter(module=m, is_active=True).order_by('sort_order')
                lessons_list = []
                for l in lessons_qs:
                    pdf_url = request.build_absolute_uri(l.pdf_file.url) if l.pdf_file else None
                    lessons_list.append({
                        'id': l.id,
                        'title': l.title,
                        'description': l.description or '',
                        'duration': l.duration,
                        'pdf_file': pdf_url,
                        'pdf_title': l.pdf_title or '',
                        'is_free': l.is_free,
                        'sort_order': l.sort_order,
                    })
                modules_list.append({
                    'id': m.id,
                    'title': m.title,
                    'sort_order': m.sort_order,
                    'lessons': lessons_list
                })

            results.append({
                'id': c.id,
                'title': c.title,
                'description': c.description or '',
                'level': c.level,
                'price': float(c.price),
                'price_180': float(c.price_180) if c.price_180 else None,
                'price_365': float(c.price_365) if c.price_365 else None,
                'price_lifetime': float(c.price_lifetime) if c.price_lifetime else None,
                'thumbnail': c.thumbnail or '',
                'is_active': c.is_active,
                'sort_order': c.sort_order,
                'modules': modules_list
            })
        return Response(results)

    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        title = request.data.get('title', '').strip()
        level = request.data.get('level', 'N5')
        description = request.data.get('description', '')
        price = request.data.get('price', 0)
        price_180 = request.data.get('price_180')
        price_365 = request.data.get('price_365')
        price_lifetime = request.data.get('price_lifetime')

        if not title:
            return Response({'error': 'กรุณาระบุชื่อคอร์สเรียน'}, status=400)

        slug = title.lower().replace(' ', '-') + '-' + str(int(time.time()))
        course = Course.objects.create(
            title=title,
            slug=slug,
            level=level,
            description=description,
            price=Decimal(str(price or 0)),
            price_180=Decimal(str(price_180)) if price_180 else None,
            price_365=Decimal(str(price_365)) if price_365 else None,
            price_lifetime=Decimal(str(price_lifetime)) if price_lifetime else None,
            is_active=True
        )
        return Response({'message': 'สร้างคอร์สเรียนใหม่เรียบร้อยแล้ว', 'id': course.id, 'title': course.title}, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return Response({'error': 'ไม่พบคอร์สนี้'}, status=404)

        if 'title' in request.data:
            course.title = request.data.get('title')
        if 'description' in request.data:
            course.description = request.data.get('description')
        if 'level' in request.data:
            course.level = request.data.get('level')
        if 'price' in request.data:
            course.price = Decimal(str(request.data.get('price') or 0))
        if 'price_180' in request.data:
            p = request.data.get('price_180')
            course.price_180 = Decimal(str(p)) if p else None
        if 'price_365' in request.data:
            p = request.data.get('price_365')
            course.price_365 = Decimal(str(p)) if p else None
        if 'price_lifetime' in request.data:
            p = request.data.get('price_lifetime')
            course.price_lifetime = Decimal(str(p)) if p else None
        course.save()
        return Response({'message': 'อัปเดตข้อมูลคอร์สเรียนเรียบร้อยแล้ว', 'id': course.id})

class AdminLessonDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        course_id = request.data.get('course_id')
        module_id = request.data.get('module_id')
        title = request.data.get('title')
        description = request.data.get('description', '')
        video_url = request.data.get('video_url', '')
        pdf_title = request.data.get('pdf_title', '')
        pdf_file = request.FILES.get('pdf_file')
        is_free = str(request.data.get('is_free', '')).lower() in ('true', '1', 'yes')

        if not course_id or not title:
            return Response({'error': 'กรุณาระบุ course_id และ title'}, status=400)

        course = Course.objects.get(pk=course_id)
        module = Module.objects.filter(pk=module_id).first() if module_id else None

        lesson = Lesson.objects.create(
            course=course,
            module=module,
            title=title,
            description=description,
            video_url=video_url,
            pdf_title=pdf_title,
            is_free=is_free
        )
        if pdf_file:
            filename, _ = save_pdf_file(pdf_file, lesson.id)
            lesson.pdf_file = filename
            lesson.save()

        return Response({
            'message': 'สร้างบทเรียนเรียบร้อยแล้ว',
            'id': lesson.id,
            'title': lesson.title
        }, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        try:
            lesson = Lesson.objects.get(pk=pk)
        except Lesson.DoesNotExist:
            return Response({'error': 'ไม่พบบทเรียนนี้'}, status=404)

        if 'title' in request.data:
            lesson.title = request.data.get('title')
        if 'description' in request.data:
            lesson.description = request.data.get('description')
        if 'video_url' in request.data:
            lesson.video_url = request.data.get('video_url')
        if 'pdf_title' in request.data:
            lesson.pdf_title = request.data.get('pdf_title')
        if 'is_free' in request.data:
            lesson.is_free = str(request.data.get('is_free')).lower() in ('true', '1', 'yes')
        if str(request.data.get('remove_pdf', '')).lower() in ('true', '1', 'yes'):
            lesson.pdf_file = ''
            lesson.pdf_title = ''
        elif request.FILES.get('pdf_file'):
            filename, _ = save_pdf_file(request.FILES.get('pdf_file'), lesson.id)
            lesson.pdf_file = filename

        lesson.save()
        return Response({'message': 'อัปเดตบทเรียนเรียบร้อยแล้ว', 'id': lesson.id})

    def delete(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        try:
            lesson = Lesson.objects.get(pk=pk)
            lesson.delete()
            return Response({'message': 'ลบบทเรียนเรียบร้อยแล้ว'})
        except Lesson.DoesNotExist:
            return Response({'error': 'ไม่พบบทเรียนนี้'}, status=404)

class AdminModuleDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        course_id = request.data.get('course_id')
        title = request.data.get('title', '').strip()
        if not course_id or not title:
            return Response({'error': 'กรุณาระบุ course_id และ title'}, status=400)
        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'ไม่พบคอร์สเรียนนี้'}, status=404)

        last_sort = Module.objects.filter(course=course).count()
        module = Module.objects.create(
            course=course,
            title=title,
            sort_order=last_sort + 1,
            is_active=True
        )
        return Response({'message': 'สร้างหมวดใหญ่เรียบร้อยแล้ว', 'id': module.id, 'title': module.title}, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        try:
            module = Module.objects.get(pk=pk)
        except Module.DoesNotExist:
            return Response({'error': 'ไม่พบหมวดนี้'}, status=404)

        title = request.data.get('title')
        if title:
            module.title = str(title).strip()
            module.save()

        return Response({'message': 'อัปเดตชื่อหมวดเรียบร้อยแล้ว', 'id': module.id, 'title': module.title})

class AdminUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        # Single user detail request
        if pk or request.GET.get('id'):
            user_id = pk or request.GET.get('id')
            try:
                u = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response({'error': 'ไม่พบรายชื่อผู้เรียนนี้'}, status=404)

            tier_info = AccessService.get_tier_progress(u.total_spent)
            courses = Course.objects.all().order_by('id')
            all_course_access = []
            for c in courses:
                enr = Enrollment.objects.filter(user=u, course=c).first()
                all_course_access.append({
                    'course_id': c.id,
                    'course_title': c.title,
                    'level': c.level,
                    'is_enrolled': bool(enr and enr.is_active),
                    'status': enr.status if enr else 'INACTIVE',
                    'is_lifetime': enr.is_lifetime_video if enr else False,
                    'expires_at': enr.video_expires_at.strftime('%Y-%m-%d') if (enr and enr.video_expires_at) else None,
                })

            return Response({
                'id': u.id,
                'name': u.name or u.email,
                'email': u.email,
                'nickname': u.nickname or '',
                'phone': u.phone or '',
                'telegram_chat_id': u.telegram_chat_id or '',
                'total_spent': float(u.total_spent),
                'points': getattr(u, 'points', 0),
                'custom_renewal_price': float(u.custom_renewal_price) if getattr(u, 'custom_renewal_price', None) is not None else None,
                'admin_remark': u.admin_remark or '',
                'tier_level': tier_info.get('current_level', 'เริ่มต้น'),
                'is_active': u.is_active,
                'created_at': u.date_joined.strftime('%d/%m/%Y') if hasattr(u, 'date_joined') and u.date_joined else '-',
                'all_course_access': all_course_access
            })

        q = request.GET.get('q', '').strip()
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        queryset = User.objects.filter(role='student').order_by('-id')
        if q:
            queryset = queryset.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(phone__icontains=q) | Q(nickname__icontains=q))

        total_count = queryset.count()
        start_idx = (page_num - 1) * page_size
        end_idx = start_idx + page_size
        page_users = queryset[start_idx:end_idx]

        results = []
        for u in page_users:
            tier_info = AccessService.get_tier_progress(u.total_spent)
            enrollments_qs = Enrollment.objects.filter(user=u, is_active=True).select_related('course')
            active_courses = [
                {
                    'course_id': e.course.id,
                    'course_title': e.course.title,
                    'level': e.course.level,
                    'status': e.status,
                    'is_lifetime': e.is_lifetime_video,
                    'expires_at': 'Lifetime' if e.is_lifetime_video else (e.video_expires_at.strftime('%d/%m/%Y') if e.video_expires_at else 'Lifetime')
                } for e in enrollments_qs
            ]

            results.append({
                'id': u.id,
                'name': u.name or u.email,
                'email': u.email,
                'nickname': u.nickname or '',
                'phone': getattr(u, 'phone', '') or '-',
                'telegram_chat_id': u.telegram_chat_id or '',
                'total_spent': float(u.total_spent),
                'points': getattr(u, 'points', 0),
                'custom_renewal_price': float(u.custom_renewal_price) if getattr(u, 'custom_renewal_price', None) is not None else None,
                'admin_remark': u.admin_remark or '',
                'tier_level': tier_info.get('current_level', 'เริ่มต้น'),
                'is_active': u.is_active,
                'created_at': u.date_joined.strftime('%d/%m/%Y') if hasattr(u, 'date_joined') and u.date_joined else '-',
                'active_courses': active_courses
            })

        return Response({
            'total': total_count,
            'page': page_num,
            'page_size': page_size,
            'results': results
        })

    @transaction.atomic
    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        email = str(request.data.get('email', '')).strip().lower()
        password = str(request.data.get('password', '')).strip()
        name = str(request.data.get('name', '')).strip()
        nickname = str(request.data.get('nickname', '')).strip()
        phone = str(request.data.get('phone', '')).strip()
        telegram_chat_id = str(request.data.get('telegram_chat_id', '')).strip()
        admin_remark = str(request.data.get('admin_remark', '')).strip()

        try:
            total_spent = Decimal(str(request.data.get('total_spent', 0)))
        except Exception:
            total_spent = Decimal('0.00')

        try:
            points = int(request.data.get('points', 0))
        except Exception:
            points = 0

        custom_price_raw = request.data.get('custom_renewal_price')
        custom_renewal_price = None
        if custom_price_raw is not None and str(custom_price_raw).strip() != '':
            try:
                custom_renewal_price = Decimal(str(custom_price_raw))
            except Exception:
                pass

        course_id = request.data.get('course_id')
        duration_days = request.data.get('duration_days', 30)
        expires_at_str = request.data.get('expires_at')

        if not email:
            return Response({'error': 'กรุณาระบุอีเมลผู้เรียน'}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({'error': f'อีเมล {email} นี้มีอยู่ในระบบเรียบร้อยแล้ว'}, status=400)

        if not password:
            password = 'Ryu' + str(int(time.time()))[-6:]

        user = User.objects.create_user(
            email=email,
            password=password,
            name=name or email,
            role='student',
            phone=phone,
            nickname=nickname,
            telegram_chat_id=telegram_chat_id,
            total_spent=total_spent,
            points=points,
            custom_renewal_price=custom_renewal_price,
            admin_remark=admin_remark
        )

        # Recalculate lifetime unlocks automatically based on initial total_spent
        AccessService.recalculate_lifetime_unlocks(user.id)

        # Grant course enrollment if specified
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                enrollment, _ = Enrollment.objects.get_or_create(
                    user=user,
                    course=course,
                    defaults={'status': 'ACTIVE', 'is_active': True}
                )
                enrollment.status = 'ACTIVE'
                enrollment.is_active = True
                enrollment.activated_at = timezone.now()
                if expires_at_str:
                    try:
                        import datetime as dt_module
                        enrollment.video_expires_at = dt_module.date.fromisoformat(str(expires_at_str))
                        enrollment.is_lifetime_video = False
                    except Exception:
                        pass
                elif duration_days:
                    days = int(duration_days)
                    if days >= 999:
                        enrollment.is_lifetime_video = True
                    else:
                        enrollment.video_expires_at = timezone.localdate() + timedelta(days=days)
                        enrollment.is_lifetime_video = False
                enrollment.save()
            except (Course.DoesNotExist, ValueError):
                pass

        return Response({
            'message': 'เพิ่มนักเรียนใหม่เข้าระบบเรียบร้อยแล้ว',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'password_used': password
            }
        }, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def put(self, request, pk=None):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        user_id = pk or request.data.get('user_id')
        if not user_id:
            return Response({'error': 'กรุณาระบุ user_id'}, status=400)

        try:
            u = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'ไม่พบรายชื่อผู้เรียนนี้'}, status=404)

        if 'name' in request.data:
            u.name = request.data.get('name')
        if 'email' in request.data and request.data.get('email'):
            new_email = str(request.data.get('email')).strip().lower()
            if new_email != u.email and not User.objects.filter(email=new_email).exclude(pk=u.id).exists():
                u.email = new_email
        if 'nickname' in request.data:
            u.nickname = request.data.get('nickname')
        if 'phone' in request.data and hasattr(u, 'phone'):
            u.phone = request.data.get('phone')
        if 'telegram_chat_id' in request.data and hasattr(u, 'telegram_chat_id'):
            u.telegram_chat_id = request.data.get('telegram_chat_id')
        if 'admin_remark' in request.data:
            u.admin_remark = request.data.get('admin_remark')

        if 'password' in request.data and request.data.get('password'):
            u.set_password(str(request.data.get('password')).strip())

        if 'points' in request.data:
            try:
                u.points = int(request.data.get('points', 0))
            except Exception:
                pass

        if 'custom_renewal_price' in request.data:
            cpr = request.data.get('custom_renewal_price')
            if cpr is None or str(cpr).strip() == '':
                u.custom_renewal_price = None
            else:
                try:
                    u.custom_renewal_price = Decimal(str(cpr))
                except Exception:
                    pass

        if 'total_spent' in request.data:
            try:
                u.total_spent = Decimal(str(request.data.get('total_spent')))
            except (ValueError, TypeError, Exception):
                pass

        u.save()

        # Recalculate lifetime unlocks automatically if total_spent changed
        AccessService.recalculate_lifetime_unlocks(u.id)

        # Handle detailed per-course enrollment updates if provided
        course_entitlements = request.data.get('course_entitlements')
        if isinstance(course_entitlements, list):
            import datetime as dt_module
            for item in course_entitlements:
                cid = item.get('course_id')
                if not cid:
                    continue
                try:
                    course = Course.objects.get(id=cid)
                    is_active = item.get('is_active', True)
                    is_lifetime = item.get('is_lifetime', False)
                    expires_str = item.get('expires_at')

                    enrollment, _ = Enrollment.objects.get_or_create(
                        user=u,
                        course=course,
                        defaults={'status': 'ACTIVE', 'is_active': True}
                    )
                    enrollment.is_active = bool(is_active)
                    enrollment.status = 'ACTIVE' if is_active else 'EXPIRED'
                    enrollment.is_lifetime_video = bool(is_lifetime)

                    if expires_str and not is_lifetime:
                        try:
                            enrollment.video_expires_at = dt_module.date.fromisoformat(str(expires_str))
                        except Exception:
                            pass
                    elif is_lifetime:
                        enrollment.video_expires_at = None

                    enrollment.save()
                except Course.DoesNotExist:
                    pass

        # Handle single course enrollment shorthand if specified
        course_id = request.data.get('course_id')
        duration_days = request.data.get('duration_days')
        expires_at_str = request.data.get('expires_at')

        if course_id and not course_entitlements:
            try:
                course = Course.objects.get(id=course_id)
                enrollment, created = Enrollment.objects.get_or_create(
                    user=u,
                    course=course,
                    defaults={'status': 'ACTIVE', 'is_active': True}
                )
                enrollment.status = 'ACTIVE'
                enrollment.is_active = True
                if expires_at_str:
                    try:
                        import datetime as dt_module
                        enrollment.video_expires_at = dt_module.date.fromisoformat(str(expires_at_str))
                        enrollment.is_lifetime_video = False
                    except Exception:
                        pass
                elif duration_days is not None:
                    days = int(duration_days)
                    if days >= 999:
                        enrollment.is_lifetime_video = True
                    else:
                        enrollment.video_expires_at = timezone.localdate() + timedelta(days=days)
                        enrollment.is_lifetime_video = False
                enrollment.save()
            except (Course.DoesNotExist, ValueError):
                pass

        return Response({'message': 'อัปเดตข้อมูลและตั้งค่านักเรียนเรียบร้อยแล้ว'})

    def delete(self, request, pk=None):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
        user_id = pk or request.data.get('user_id')
        try:
            u = User.objects.get(pk=user_id)
            u.is_active = False
            u.save()
            return Response({'message': 'ปิดใช้งานบัญชีผู้เรียนเรียบร้อยแล้ว'})
        except User.DoesNotExist:
            return Response({'error': 'ไม่พบรายชื่อผู้เรียนนี้'}, status=404)


class AdminUserImportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        students_data = request.data.get('students', [])
        if not isinstance(students_data, list) or len(students_data) == 0:
            return Response({'error': 'กรุณาระบุรายการนักเรียนในรูปแบบ array (students)'}, status=400)

        imported_count = 0
        updated_count = 0
        errors = []

        import datetime as dt_module

        for idx, row in enumerate(students_data):
            try:
                email = str(row.get('email', '')).strip().lower()
                if not email:
                    errors.append(f"แถวที่ {idx+1}: ไม่พบอีเมลผู้เรียน")
                    continue

                name = str(row.get('name', email)).strip()
                phone = str(row.get('phone', '')).strip()
                nickname = str(row.get('nickname', '')).strip()
                password = str(row.get('password', '')).strip()
                admin_remark = str(row.get('admin_remark', 'Imported from legacy system')).strip()

                try:
                    total_spent = Decimal(str(row.get('total_spent', 0)))
                except Exception:
                    total_spent = Decimal('0.00')

                try:
                    points = int(row.get('points', 0))
                except Exception:
                    points = 0

                custom_price_raw = row.get('custom_renewal_price')
                custom_renewal_price = None
                if custom_price_raw is not None and str(custom_price_raw).strip() != '':
                    try:
                        custom_renewal_price = Decimal(str(custom_price_raw))
                    except Exception:
                        pass

                user = User.objects.filter(email=email).first()
                if user:
                    user.name = name or user.name
                    if phone:
                        user.phone = phone
                    if nickname:
                        user.nickname = nickname
                    user.total_spent = total_spent
                    user.points = points
                    user.custom_renewal_price = custom_renewal_price
                    user.admin_remark = admin_remark
                    user.save()
                    updated_count += 1
                else:
                    pwd_used = password or ('Ryu' + str(int(time.time()))[-6:])
                    user = User.objects.create_user(
                        email=email,
                        password=pwd_used,
                        name=name,
                        role='student',
                        phone=phone,
                        nickname=nickname,
                        total_spent=total_spent,
                        points=points,
                        custom_renewal_price=custom_renewal_price,
                        admin_remark=admin_remark
                    )
                    imported_count += 1

                # Lifetime levels unlock automatically based on total_spent
                AccessService.recalculate_lifetime_unlocks(user.id)

                # Manual lifetime levels or active course enrollments override
                lifetime_levels = row.get('lifetime_levels') # e.g. "N5,N4" or ["N5", "N4"]
                if isinstance(lifetime_levels, str):
                    lifetime_levels = [l.strip().upper() for l in lifetime_levels.split(',') if l.strip()]

                if isinstance(lifetime_levels, list):
                    for lvl in lifetime_levels:
                        courses_qs = Course.objects.filter(level=lvl.upper(), is_active=True)
                        for course in courses_qs:
                            enr, _ = Enrollment.objects.get_or_create(user=user, course=course)
                            enr.is_active = True
                            enr.status = 'ACTIVE'
                            enr.is_lifetime_video = True
                            enr.save()
            except Exception as row_err:
                import traceback
                traceback.print_exc()
                errors.append(f"แถวที่ {idx+1} ({row.get('email', 'N/A')}): {str(row_err)}")

        return Response({
            'message': f'นำเข้าเรียบร้อย: เพิ่มใหม่ {imported_count} รายการ, อัปเดต {updated_count} รายการ',
            'imported_count': imported_count,
            'updated_count': updated_count,
            'errors': errors
        })


class AdminBroadcastEmailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        target = request.data.get('target', 'all')
        subject = request.data.get('subject', '').strip()
        body = request.data.get('body', '').strip()

        if not subject or not body:
            return Response({'error': 'กรุณากรอกหัวข้อและเนื้อหาอีเมลให้ครบถ้วน'}, status=400)

        recipients = User.objects.filter(role='student', is_active=True)
        if target.startswith('course_'):
            course_id = target.replace('course_', '')
            user_ids = Enrollment.objects.filter(course_id=course_id, is_active=True).values_list('user_id', flat=True)
            recipients = recipients.filter(id__in=user_ids)
        elif target == 'active':
            user_ids = Enrollment.objects.filter(is_active=True, status='ACTIVE').values_list('user_id', flat=True)
            recipients = recipients.filter(id__in=user_ids)
        elif target == 'expired':
            user_ids = Enrollment.objects.filter(status='EXPIRED').values_list('user_id', flat=True)
            recipients = recipients.filter(id__in=user_ids)

        email_list = list(recipients.values_list('email', flat=True).distinct())

        if not email_list:
            return Response({'error': 'ไม่พบอีเมลผู้เรียนในกลุ่มที่เลือก'}, status=404)

        from django.core.mail import EmailMultiAlternatives
        sent_success = 0
        for email_addr in email_list:
            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@chatbotth.me'),
                    to=[email_addr]
                )
                msg.attach_alternative(body.replace('\n', '<br>'), "text/html")
                msg.send(fail_silently=True)
                sent_success += 1
            except Exception:
                pass

        return Response({
            'message': f'ส่งอีเมลสำเร็จ {sent_success} / {len(email_list)} บัญชีเรียบร้อยแล้ว!',
            'sent_count': sent_success,
            'total_target': len(email_list)
        })
