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
        except (ValueError, TypeError):
            return Response({'error': 'ระยะเวลาเรียนไม่ถูกต้อง'}, status=400)

        # Check existing enrollment for renewal eligibility
        enrollment = Enrollment.objects.filter(
            user=user, course=course, is_active=True, is_lifetime_video=False,
        ).first()
        
        is_renewal = False
        bonus_days = getattr(settings, 'RENEWAL_BONUS_DAYS', 3)
        if renewal_requested or enrollment:
            is_renewal = True
            if requested_days == 30:
                requested_days = 30 + bonus_days
        
        try:
            amount = package_amount(course, 30 if requested_days == (30 + bonus_days) else requested_days)
        except (ValueError, TypeError) as exc:
            return Response({'error': str(exc)}, status=400)
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
