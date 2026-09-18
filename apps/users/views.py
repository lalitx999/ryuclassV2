import os
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from django.conf import settings
from .models import User
from .utils import notify_admin_new_order
from payments.models import Payment
from courses.models import Course, Enrollment

class LoginView(APIView):
    def post(self, request):
        try:
            email = request.data.get('email') or request.data.get('username')
            password = request.data.get('password')

            if not email or not password:
                return Response({'detail': 'กรุณากรอกอีเมลและรหัสผ่านให้ครบถ้วนครับ'}, status=status.HTTP_400_BAD_REQUEST)

            email_clean = str(email).strip().lower()
            try:
                user = User.objects.get(email__iexact=email_clean)
            except User.DoesNotExist:
                return Response({'detail': 'อีเมลหรือรหัสผ่านไม่ถูกต้องครับ'}, status=status.HTTP_400_BAD_REQUEST)

            if not user.check_password(password):
                return Response({'detail': 'อีเมลหรือรหัสผ่านไม่ถูกต้องครับ'}, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_active:
                return Response({'detail': 'บัญชีผู้ใช้นี้ถูกระงับการใช้งาน'}, status=status.HTTP_400_BAD_REQUEST)

            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role,
                    'nickname': user.nickname,
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'detail': f'เกิดข้อผิดพลาดทางเทคนิคที่เซิร์ฟเวอร์: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegisterView(APIView):
    @transaction.atomic
    def post(self, request):
        name = request.data.get('name')
        nickname = request.data.get('nickname')
        email = request.data.get('email')
        password = request.data.get('password')
        phone = request.data.get('phone')
        level = request.data.get('level')
        duration = request.data.get('duration')
        slip_file = request.FILES.get('slip')

        if not name or not email or not password or not phone or not level or not duration or not slip_file:
            return Response(
                {'error': 'กรุณากรอกข้อมูลและแนบสลิปการโอนเงินให้ครบถ้วนทุกช่องครับ'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'อีเมลนี้ถูกใช้งานสมัครเรียนแล้ว หากต้องการเรียนเพิ่มหรือต่ออายุ กรุณาเข้าสู่ระบบก่อนครับ'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 1. Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                name=name,
                nickname=nickname,
                phone=phone,
                role='student'
            )

            # 2. Get Course ID mapping
            course_map = {'N5': 1, 'N4': 2, 'N3': 3, 'N2': 4, 'N1': 5}
            course_id = course_map.get(level, 1)
            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:
                return Response({'error': 'ไม่พบคอร์สเรียนที่เลือก'}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Calculate Amount
            price_matrix = {
                'N5': {30: 1.0, 180: 5000.0, 365: 9000.0, 9999: 10000.0},
                'N4': {30: 1250.0, 180: 6500.0, 365: 12000.0, 9999: 20000.0},
                'N3': {30: 1500.0, 180: 8000.0, 365: 15000.0, 9999: 30000.0},
                'N2': {30: 1750.0, 180: 9500.0, 365: 18000.0, 9999: 40000.0},
                'N1': {30: 2000.0, 180: 11000.0, 365: 21000.0, 9999: 50000.0},
            }
            amount = price_matrix.get(level, {}).get(int(duration), 1000.0)

            # 4. Save Slip File
            ext = os.path.splitext(slip_file.name)[1] or '.jpg'
            filename = f"slip_{user.id}_{int(time.time())}{ext}"
            
            # Save to XAMPP storage for preview
            storage_path = '/Applications/XAMPP/xamppfiles/htdocs/ryuclass/storage/slips/'
            os.makedirs(storage_path, exist_ok=True)
            target_path = os.path.join(storage_path, filename)
            
            with open(target_path, 'wb+') as destination:
                for chunk in slip_file.chunks():
                    destination.write(chunk)

            # 5. Create Payment
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

            # 6. Notify Admin via Telegram
            notify_admin_new_order(
                payment_id=payment.id,
                student_name=user.name,
                student_email=user.email,
                course_name=course.title,
                amount=amount
            )

            # 7. Generate tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'ลงทะเบียนเรียบร้อยแล้ว กรุณารอแอดมินตรวจสอบสลิปภายใน 24 ชม.',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'email': user.email,
                    'name': user.name,
                    'role': user.role
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'เกิดข้อผิดพลาด: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        enrollments = Enrollment.objects.filter(user=user, is_active=True)
        courses_access = []
        for e in enrollments:
            courses_access.append({
                'course_id': e.course_id,
                'course_title': e.course.title,
                'is_lifetime': e.is_lifetime_video,
                'video_expires_at': e.video_expires_at,
                'zoom_expires_at': e.zoom_expires_at,
            })
            
        return Response({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'nickname': user.nickname,
            'phone': user.phone,
            'total_spent': user.total_spent,
            'is_affiliate': user.is_affiliate,
            'courses_access': courses_access
        }, status=status.HTTP_200_REST_OK if hasattr(status, 'HTTP_200_REST_OK') else status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        name = request.data.get('name')
        nickname = request.data.get('nickname')
        phone = request.data.get('phone')
        password = request.data.get('password')

        if name:
            user.name = name
        if nickname:
            user.nickname = nickname
        if phone:
            user.phone = phone
        if password:
            user.set_password(password)
            
        user.save()
        return Response({'message': 'อัปเดตข้อมูลโปรไฟล์เรียบร้อยแล้ว'})
