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
from payments.models import Payment, SlipVerificationLog
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
            user = User.objects.select_for_update().get(pk=payment.user_id)
            user.total_spent += Decimal(str(payment.amount))
            user.save(update_fields=['total_spent'])
            AccessService.recalculate_lifetime_unlocks(user.pk)

            enrollment, _ = Enrollment.objects.get_or_create(user=user, course=payment.course)
            enrollment.is_active = True
            enrollment.status = 'ACTIVE'
            enrollment.payment_id = payment.pk
            enrollment.activated_at = timezone.now()

            if payment.duration_days == 9999:
                enrollment.is_lifetime_video = True
            else:
                base_date = max(enrollment.video_expires_at or timezone.localdate(), timezone.localdate())
                enrollment.video_expires_at = base_date + timedelta(days=payment.duration_days)
                if payment.is_zoom_included:
                    zoom_base = max(enrollment.zoom_expires_at or timezone.localdate(), timezone.localdate())
                    enrollment.zoom_expires_at = zoom_base + timedelta(days=payment.duration_days)
            enrollment.save()

            payment.status = 'approved'
            payment.rejection_reason = ''
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
            lesson.pdf_file = pdf_file
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
        if request.FILES.get('pdf_file'):
            lesson.pdf_file = request.FILES.get('pdf_file')

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

class AdminUsersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_staff_member(request.user):
            return Response({'error': 'เฉพาะผู้ดูแลระบบเท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        q = request.GET.get('q', '').strip()
        page_num = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        queryset = User.objects.filter(role='student').order_by('-id')
        if q:
            queryset = queryset.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(phone__icontains=q))

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
                    'status': e.status,
                    'expires_at': e.video_expires_at.strftime('%d/%m/%Y') if e.video_expires_at else 'Lifetime'
                } for e in enrollments_qs
            ]

            results.append({
                'id': u.id,
                'name': u.name or u.email,
                'email': u.email,
                'phone': getattr(u, 'phone', '') or '-',
                'total_spent': float(u.total_spent),
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
