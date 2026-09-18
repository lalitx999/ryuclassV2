import os
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Payment
from courses.models import Course
from users.utils import notify_admin_new_order

class UploadSlipView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        course_id = request.data.get('course_id')
        duration = request.data.get('duration')
        slip_file = request.FILES.get('slip')

        if not course_id or not duration or not slip_file:
            return Response(
                {'error': 'กรุณากรอกข้อมูลและแนบสลิปการโอนเงินให้ครบถ้วนครับ'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'ไม่พบคอร์สเรียน'}, status=status.HTTP_400_BAD_REQUEST)

        # Map levels and calculate amount
        course_level_map = {1: 'N5', 2: 'N4', 3: 'N3', 4: 'N2', 5: 'N1'}
        level = course_level_map.get(course.id, 'N5')

        price_matrix = {
            'N5': {30: 1.0, 180: 5000.0, 365: 9000.0, 9999: 10000.0},
            'N4': {30: 1250.0, 180: 6500.0, 365: 12000.0, 9999: 20000.0},
            'N3': {30: 1500.0, 180: 8000.0, 365: 15000.0, 9999: 30000.0},
            'N2': {30: 1750.0, 180: 9500.0, 365: 18000.0, 9999: 40000.0},
            'N1': {30: 2000.0, 180: 11000.0, 365: 21000.0, 9999: 50000.0},
        }
        amount = price_matrix.get(level, {}).get(int(duration), 1000.0)

        try:
            # Save Slip File
            ext = os.path.splitext(slip_file.name)[1] or '.jpg'
            filename = f"slip_{user.id}_{int(time.time())}{ext}"
            
            storage_path = '/Applications/XAMPP/xamppfiles/htdocs/ryuclass/storage/slips/'
            os.makedirs(storage_path, exist_ok=True)
            target_path = os.path.join(storage_path, filename)
            
            with open(target_path, 'wb+') as destination:
                for chunk in slip_file.chunks():
                    destination.write(chunk)

            # Create Payment
            payment = Payment.objects.create(
                user=user,
                course=course,
                amount=amount,
                duration_days=int(duration),
                level_access=level,
                is_zoom_included=(int(duration) >= 180),
                slip_path=filename,
                status='pending'
            )

            # Notify Admin via Telegram
            notify_admin_new_order(
                payment_id=payment.id,
                student_name=user.name,
                student_email=user.email,
                course_name=course.title,
                amount=amount
            )

            return Response({
                'message': 'อัปโหลดสลิปเรียบร้อยแล้ว กรุณารอแอดมินตรวจสอบสลิปภายใน 24 ชม.',
                'payment_id': payment.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'เกิดข้อผิดพลาด: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
