import os
import time
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from courses.pricing import package_amount
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from django.conf import settings
from .utils import save_slip_file, verify_slip_easyslip
from .models import Payment
from courses.models import Course, Enrollment
from users.utils import notify_admin_new_order

class UploadSlipView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        course_id = request.data.get('course_id')
        duration = request.data.get('duration')
        renewal_requested = str(request.data.get('renewal', '')).lower() in ('1', 'true', 'yes')
        slip_file = request.FILES.get('slip')

        if not course_id or not duration or not slip_file:
            return Response(
                {'error': 'กรุณากรอกข้อมูลและแนบสลิปการโอนเงินให้ครบถ้วนครับ'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            course = Course.objects.get(id=course_id, is_active=True)
        except Course.DoesNotExist:
            return Response({'error': 'ไม่พบคอร์สเรียน'}, status=status.HTTP_400_BAD_REQUEST)

        # Map levels and calculate amount
        course_level_map = {1: 'N5', 2: 'N4', 3: 'N3', 4: 'N2', 5: 'N1'}
        level = course_level_map.get(course.id, 'N5')

        try:
            requested_days = int(duration)
            amount = package_amount(course, 30 if renewal_requested else requested_days)
        except (ValueError, TypeError) as exc:
            return Response({'error': str(exc)}, status=400)
        is_renewal = False
        discount_percent = 0

        # The browser may request renewal, but the server decides eligibility.
        enrollment = Enrollment.objects.filter(
            user=user, course=course, is_active=True, is_lifetime_video=False,
        ).first()
        today = timezone.now().date()
        if renewal_requested and enrollment and enrollment.video_expires_at:
            days_remaining = (enrollment.video_expires_at - today).days
            if 0 <= days_remaining <= 3:
                is_renewal = True
                discount_percent = 10
                requested_days = 33
                amount = (Decimal(str(course.price)) * Decimal('0.90')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if renewal_requested and not is_renewal:
            return Response({'error': 'ยังไม่เข้าเงื่อนไขส่วนลดต่ออายุ กรุณาเลือกแพ็กเกจปกติ'}, status=400)
        try:
            expected = Decimal(str(request.data.get('expected_amount', '')))
            if not expected.is_finite() or expected != amount:
                return Response({'error': 'ราคามีการเปลี่ยนแปลง กรุณาปิดแล้วเปิดหน้าชำระเงินใหม่เพื่อตรวจสอบยอดก่อนโอน'}, status=409)
        except InvalidOperation:
            return Response({'error': 'กรุณาโหลดหน้าชำระเงินใหม่เพื่อยืนยันราคา'}, status=400)

        try:
            # Save Slip File with fallback
            filename, target_path = save_slip_file(slip_file, user.id)

            # Create Payment
            payment = Payment.objects.create(
                user=user,
                course=course,
                amount=amount,
                duration_days=requested_days,
                level_access=level,
                is_zoom_included=(requested_days >= 180),
                slip_path=filename,
                status='pending',
                is_renewal=is_renewal,
                discount_percent=discount_percent,
            )

            # EasySlip Verification & Auto Approval
            easyslip_ok, easyslip_msg, _ = verify_slip_easyslip(payment, target_path)
            payment.refresh_from_db()

            # Notify Admin via Telegram
            notify_admin_new_order(
                payment_id=payment.id,
                student_name=user.name or user.email,
                student_email=user.email,
                course_name=course.title,
                amount=float(amount),
                phone=getattr(user, 'phone', ''),
                level=level,
                duration=requested_days,
                slip_file_path=target_path
            )

            response_msg = 'อัปโหลดสลิปและอนุมัติสิทธิ์การเรียนให้อัตโนมัติเรียบร้อยแล้ว!' if payment.status == 'approved' else 'อัปโหลดสลิปเรียบร้อยแล้ว กรุณารอแอดมินตรวจสอบสลิปภายใน 24 ชม.'

            return Response({
                'message': response_msg,
                'payment_id': payment.id,
                'status': payment.status,
                'verification_message': easyslip_msg
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'เกิดข้อผิดพลาด: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
