import os
import secrets
import time
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils import timezone
from .models import EmailVerificationCode, User
from .utils import notify_admin_new_order
from payments.models import Payment
from courses.models import Course, Enrollment


VERIFICATION_CODE_TTL_MINUTES = 10
VERIFICATION_RESEND_WAIT_SECONDS = 60
VERIFICATION_MAX_ATTEMPTS = 5


def create_and_send_verification_code(user):
    """Invalidate previous challenges, then email a fresh six-digit OTP."""
    now = timezone.now()
    EmailVerificationCode.objects.filter(user=user, verified_at__isnull=True).update(expires_at=now)
    code = f'{secrets.randbelow(1_000_000):06d}'
    EmailVerificationCode.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=now + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES),
    )
    send_mail(
        subject='รหัสยืนยันอีเมล RyuClass',
        message=(
            f'สวัสดีครับ {user.name or "นักเรียน RyuClass"}\n\n'
            f'รหัสยืนยันอีเมลของคุณคือ: {code}\n'
            f'รหัสนี้ใช้ได้ {VERIFICATION_CODE_TTL_MINUTES} นาที และห้ามบอกรหัสนี้กับผู้อื่น\n\n'
            'ทีมงาน RyuClass'
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        recipient_list=[user.email],
        fail_silently=False,
    )

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

            pending_verification = EmailVerificationCode.objects.filter(user=user, verified_at__isnull=True).exists()
            if pending_verification and not user.email_verified:
                return Response({
                    'detail': 'กรุณายืนยันอีเมลด้วยรหัส 6 หลักก่อนเข้าสู่ระบบ',
                    'verification_required': True,
                }, status=status.HTTP_403_FORBIDDEN)

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
                'N5': {30: 1000.0, 180: 5000.0, 365: 9000.0, 9999: 10000.0},
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

            # 7. Send a six-digit verification code before allowing login.
            try:
                create_and_send_verification_code(user)
            except Exception:
                transaction.set_rollback(True)
                return Response(
                    {'error': 'ไม่สามารถส่งรหัสยืนยันอีเมลได้ กรุณาลองสมัครใหม่อีกครั้งในภายหลัง'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response({
                'message': 'ลงทะเบียนเรียบร้อยแล้ว กรุณาตรวจสอบอีเมลและกรอกรหัส 6 หลักเพื่อยืนยันบัญชี',
                'verification_required': True,
                'user': {
                    'email': user.email,
                    'name': user.name,
                    'role': user.role
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': f'เกิดข้อผิดพลาด: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyEmailView(APIView):
    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        code = str(request.data.get('code', '')).strip()
        if not email or not code.isdigit() or len(code) != 6:
            return Response({'error': 'กรุณากรอกอีเมลและรหัสยืนยัน 6 หลักให้ครบถ้วน'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'error': 'รหัสยืนยันไม่ถูกต้องหรือหมดอายุ'}, status=status.HTTP_400_BAD_REQUEST)

        challenge = EmailVerificationCode.objects.filter(user=user, verified_at__isnull=True).first()
        if not challenge or challenge.expires_at <= timezone.now():
            return Response({'error': 'รหัสยืนยันหมดอายุ กรุณาขอรหัสใหม่'}, status=status.HTTP_400_BAD_REQUEST)
        if challenge.attempts >= VERIFICATION_MAX_ATTEMPTS:
            return Response({'error': 'กรอกรหัสผิดเกินกำหนด กรุณาขอรหัสใหม่'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        challenge.attempts += 1
        if not check_password(code, challenge.code_hash):
            challenge.save(update_fields=['attempts'])
            return Response({'error': 'รหัสยืนยันไม่ถูกต้อง'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        challenge.verified_at = now
        challenge.save(update_fields=['attempts', 'verified_at'])
        user.email_verified = True
        user.save(update_fields=['email_verified'])

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'ยืนยันอีเมลเรียบร้อยแล้ว',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'email': user.email, 'name': user.name, 'role': user.role},
        })


class ResendEmailVerificationView(APIView):
    def post(self, request):
        email = str(request.data.get('email', '')).strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if not user or user.email_verified:
            return Response({'message': 'หากอีเมลนี้รอการยืนยัน ระบบจะส่งรหัสใหม่ให้'}, status=status.HTTP_200_OK)

        latest = EmailVerificationCode.objects.filter(user=user, verified_at__isnull=True).first()
        if latest and (timezone.now() - latest.sent_at).total_seconds() < VERIFICATION_RESEND_WAIT_SECONDS:
            return Response({'error': 'กรุณารอ 1 นาทีก่อนขอรหัสใหม่'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            create_and_send_verification_code(user)
        except Exception:
            return Response({'error': 'ไม่สามารถส่งรหัสใหม่ได้ กรุณาลองอีกครั้งภายหลัง'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'message': 'ส่งรหัสยืนยันใหม่ไปยังอีเมลแล้ว'})

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

class BroadcastEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'admin' and not request.user.is_staff:
            return Response({'error': 'เฉพาะแอดมินเท่านั้นที่มีสิทธิ์ส่งอีเมลบรอดแคสต์'}, status=status.HTTP_403_FORBIDDEN)

        subject = request.data.get('subject')
        message = request.data.get('message')
        target_role = request.data.get('target_role', 'all')

        if not subject or not message:
            return Response({'error': 'กรุณาระบุหัวข้อ (subject) และเนื้อหา (message) ของอีเมล'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = User.objects.filter(is_active=True)
        if target_role == 'student':
            queryset = queryset.filter(role='student')
        elif target_role == 'admin':
            queryset = queryset.filter(role='admin')

        recipient_list = list(queryset.values_list('email', flat=True))
        if not recipient_list:
            return Response({'error': 'ไม่พบรายชื่ออีเมลผู้ใช้งานที่ตรงตามเงื่อนไข'}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.mail import EmailMultiAlternatives
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'RyuClass <support@chatbotth.me>')

        success_count = 0
        for recipient in recipient_list:
            try:
                email_msg = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=[recipient]
                )
                email_msg.send(fail_silently=True)
                success_count += 1
            except Exception:
                pass

        return Response({
            'message': f'บรอดแคสต์ส่งอีเมลสำเร็จแล้ว {success_count}/{len(recipient_list)} รายชื่อ',
            'total_sent': success_count,
            'total_target': len(recipient_list)
        }, status=status.HTTP_200_OK)
