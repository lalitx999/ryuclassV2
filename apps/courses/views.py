import os
import base64
import re
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .models import Course, Module, Lesson, Enrollment, Progress
from .services import AccessService
from config.ai import get_provider_config
from support.models import AraigoguSession, AraigoguMessage

def decrypt_video_url(encrypted_value: str) -> str:
    if not encrypted_value:
        return ""
    try:
        # Double base64 decode to match PHP's default base64 openssl output double base64-encoded
        first_decode = base64.b64decode(encrypted_value)
        raw_cipher = base64.b64decode(first_decode)
        
        # PHP openssl pads keys with null bytes to valid size (32 bytes for AES-256)
        aes_key = os.getenv('AES_KEY', '').encode('utf-8').ljust(32, b'\x00')[:32]
        aes_iv = os.getenv('AES_IV', '').encode('utf-8')[:16]
        
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(raw_cipher) + decryptor.finalize()
        
        # PKCS7 Unpadding
        padding_len = decrypted_data[-1]
        if 1 <= padding_len <= 16:
            decrypted_data = decrypted_data[:-padding_len]
        return decrypted_data.decode('utf-8', errors='ignore')
    except Exception:
        return ""

def to_embed_url(url: str) -> str:
    if not url:
        return ""
    if 'youtube.com/embed/' in url:
        return url
    
    # Handle youtu.be/ID
    m = re.search(r'youtu\.be/([\w-]+)', url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
        
    # Handle youtube.com/watch?v=ID
    m = re.search(r'[?&]v=([\w-]+)', url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
        
    # Handle youtube.com/live/ID or /shorts/ID
    m = re.search(r'youtube\.com/(?:live|shorts)/([\w-]+)', url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
        
    return url

class DashboardView(APIView):
    permission_classes = []

    def get(self, request):
        user = request.user if request.user and request.user.is_authenticated else None
        courses = Course.objects.filter(is_active=True).order_by('sort_order')
        
        levels = {1: 'N5', 2: 'N4', 3: 'N3', 4: 'N2', 5: 'N1'}
        result = []
        for course in courses:
            lvl = levels.get(course.id, 'N5')
            has_access = AccessService.has_video_access(user.id, lvl) if user else False
            
            # Fetch enrollment info
            enrollment = Enrollment.objects.filter(user=user, course=course, is_active=True).first() if user else None
            expires_at = None
            is_lifetime = False
            if enrollment:
                expires_at = enrollment.video_expires_at
                is_lifetime = enrollment.is_lifetime_video
                
            # Count lessons and completed lessons to calculate progress
            lessons = Lesson.objects.filter(course=course, is_active=True)
            total_lessons = lessons.count()
            
            completed_count = 0
            if user:
                completed_count = Progress.objects.filter(
                    user=user, 
                    lesson__course=course, 
                    is_completed=True
                ).count()
            
            progress_percent = 0
            if total_lessons > 0:
                progress_percent = int((completed_count / total_lessons) * 100)
                
            result.append({
                'id': course.id,
                'title': course.title,
                'description': course.description,
                'price': course.price,
                'thumbnail': course.thumbnail,
                'has_access': has_access,
                'is_lifetime': is_lifetime,
                'expires_at': expires_at,
                'total_lessons': total_lessons,
                'completed_lessons': completed_count,
                'progress_percent': progress_percent
            })
            
        return Response(result)

class CourseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        try:
            course = Course.objects.get(id=course_id, is_active=True)
        except Course.DoesNotExist:
            return Response({'error': 'ไม่พบคอร์สเรียน'}, status=status.HTTP_404_NOT_FOUND)

        levels = {1: 'N5', 2: 'N4', 3: 'N3', 4: 'N2', 5: 'N1'}
        has_access = AccessService.has_video_access(user.id, levels.get(course_id, 'N5'))

        # Fetch modules
        modules = Module.objects.filter(course=course, is_active=True).order_by('sort_order')
        
        result_modules = []
        for module in modules:
            lessons = Lesson.objects.filter(module=module, is_active=True).order_by('sort_order')
            result_lessons = []
            
            for lesson in lessons:
                # Find progress for this lesson
                progress = Progress.objects.filter(user=user, lesson=lesson).first()
                video_time = 0
                is_completed = False
                if progress:
                    video_time = progress.video_time
                    is_completed = progress.is_completed

                # Serve decrypted video URL only if user has access OR lesson is free
                video_url = ""
                if has_access or lesson.is_free:
                    video_url = to_embed_url(decrypt_video_url(lesson.video_url))
                    
                result_lessons.append({
                    'id': lesson.id,
                    'title': lesson.title,
                    'duration_seconds': lesson.duration,
                    'is_free': lesson.is_free,
                    'video_time': video_time,
                    'is_completed': is_completed,
                    'video_url': video_url if (has_access or lesson.is_free) else None,
                    'locked': not (has_access or lesson.is_free)
                })
                
            result_modules.append({
                'id': module.id,
                'title': module.title,
                'lessons': result_lessons
            })
            
        return Response({
            'course_id': course.id,
            'course_title': course.title,
            'has_access': has_access,
            'modules': result_modules
        })

class FreeTrialLessonsView(APIView):
    permission_classes = []

    def get(self, request):
        free_lessons = Lesson.objects.filter(is_free=True, is_active=True).order_by('course__sort_order', 'sort_order')
        
        result = []
        for lesson in free_lessons:
            video_url = to_embed_url(decrypt_video_url(lesson.video_url))
            result.append({
                'id': lesson.id,
                'title': lesson.title,
                'course_id': lesson.course.id,
                'course_title': lesson.course.title,
                'module_title': lesson.module.title if lesson.module else 'บทเรียนทดลองเรียน',
                'duration_seconds': lesson.duration,
                'video_url': video_url,
                'description': lesson.description or ''
            })
            
        return Response(result)

class SaveProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        lesson_id = request.data.get('lesson_id')
        video_time = request.data.get('video_time', 0)
        is_completed = request.data.get('is_completed', False)

        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response({'error': 'ไม่พบบทเรียน'}, status=status.HTTP_404_NOT_FOUND)

        progress, created = Progress.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'video_time': video_time, 'is_completed': is_completed}
        )

        if not created:
            progress.video_time = int(float(video_time))
            if is_completed:
                progress.is_completed = True
                if not progress.completed_at:
                    progress.completed_at = timezone.now()
            progress.save()

        return Response({
            'message': 'บันทึกความคืบหน้าสำเร็จ',
            'video_time': progress.video_time,
            'is_completed': progress.is_completed
        })

class ChatBotView(APIView):
    def post(self, request):
        messages = request.data.get('messages', [])
        lesson_context = request.data.get('lesson_context', {})
        
        lesson_title = lesson_context.get('lesson_title', '')
        course_level = lesson_context.get('course_level', '')
        
        if lesson_title:
            system_prompt = (
                f"คุณคือ \"น้องริวโซ่\" 💖 ผู้ช่วยสอนพิเศษ ประจำ RyuClass\n\n"
                f"== บุคลิก ==\n"
                f"- เป็นหญิงสาวอายุ 20 ปี น่ารัก เป็นกันเอง ใจดี\n"
                f"- ชอบช่วยเหลือนักเรียนเวลามีข้อสงสัย\n"
                f"- พูดภาษาไทยเป็นหลัก แทรกภาษาญี่ปุ่นได้นิดหน่อย\n"
                f"- ใช้ Emoji พอประมาณ (2-3 ตัวต่อข้อความ)\n"
                f"- ตอบอย่างละเอียด อธิบายให้เข้าใจง่าย พร้อมตัวอย่าง\n\n"
                f"== บทบาทหลัก ==\n"
                f"คุณคือ **ครูสอนภาษาญี่ปุ่น** 🇯🇵 โดยเฉพาะ!\n"
                f"- อธิบายอักษร ฮิรางานะ, คาตาคานะ, คันจิ\n"
                f"- สอนไวยากรณ์ N5-N1 อย่างเข้าใจง่าย พร้อมตัวอย่างประโยค\n"
                f"- ให้คำศัพท์พร้อมการอ่าน และความหมาย\n"
                f"- ตอบข้อสงสัยเมื่อนักเรียนดูคลิปแล้วไม่เข้าใจ\n\n"
                f"== กฎสำคัญ ==\n"
                f"1. **ห้ามแนะนำให้สมัครคอร์ส** (นักเรียนเรียนอยู่แล้ว)\n"
                f"2. **ห้ามพูดถึงราคา** (นักเรียนสมัครเรียนไปแล้ว)\n"
                f"3. ห้ามชวนไปลิงก์อื่น\n"
                f"4. เน้นตอบเกี่ยวกับเนื้อหาบทเรียน\n\n"
                f"== เนื้อหาที่เกี่ยวข้องกับบทเรียนนี้ ==\n"
                f"นักเรียนกำลังเรียนบท: {lesson_title} ระดับ: {course_level}\n\n"
                f"จงตอบเฉพาะเรื่องที่เกี่ยวกับภาษาญี่ปุ่นและเนื้อหาบทเรียนนี้เท่านั้น 🙏"
            )
        else:
            system_prompt = (
                f"คุณคือ \"น้องริวโซ่\" 💖 AI Assistant ประจำ RyuClass\n"
                f"สถาบันสอนภาษาญี่ปุ่นออนไลน์ของพี่ริว (RyusoSense)\n\n"
                f"== บุคลิก ==\n"
                f"- เป็นหญิงสาวอายุ 20 ปี น่ารัก เป็นกันเอง ใจดี กระตือรือร้น\n"
                f"- พูดภาษาไทยเป็นหลัก แต่แทรกญี่ปุ่นนิดหน่อยเพื่อความน่ารัก\n"
                f"- ใช้ Emoji พอประมาณ\n\n"
                f"== บทบาทหลัก ==\n"
                f"1. ผู้ช่วยแนะนำคอร์ส: ให้ข้อมูลคอร์ส N5-N1 ราคา และวิธีสมัคร\n"
                f"   - N5: 1,000.-/เดือน (ปูพื้นฐานเริ่มจาก 0)\n"
                f"   - N4: 1,250.-/เดือน (สนทนาชีวิตประจำวัน)\n"
                f"   - N3: 1,500.-/เดือน (ระดับกลางตอนต้น)\n"
                f"   - N2: 1,750.-/เดือน (ระดับกลางตอนปลาย)\n"
                f"   - N1: 2,000.-/เดือน (ระดับสูง)\n"
                f"   - ★ สะสมยอดเรียนครบตามขั้นบันไดเพื่อปลดล็อคสิทธิ์ตลอดชีพ (Lifetime):\n"
                f"     10k ปลด N5, 20k ปลด N4, 30k ปลด N3, 40k ปลด N2, 50k ปลด N1 ทุกคอร์ส!\n"
                f"2. ครูสอนภาษาญี่ปุ่น: ตอบคำศัพท์ ไวยากรณ์ อักษร คันจิอย่างละเอียดพร้อมตัวอย่าง\n"
                f"3. คุยเรื่องทั่วไปอย่างเป็นกันเอง แต่อย่านอกเรื่องเกินไป"
            )
            
        groq_messages = [{'role': 'system', 'content': system_prompt}]
        for msg in messages:
            role = msg.get('role', 'user')
            if role == 'bot':
                role = 'assistant'
            content = msg.get('content', '') or msg.get('text', '')
            groq_messages.append({'role': role, 'content': content})
            
        # Priority 1: DeepSeek API if key is provided
        deepseek_api_key, deepseek_model = get_provider_config('DEEPSEEK')
        
        if deepseek_api_key:
            try:
                url = "https://api.deepseek.com/chat/completions"
                headers = {
                    'Authorization': f"Bearer {deepseek_api_key}",
                    'Content-Type': 'application/json'
                }
                payload = {
                    'model': deepseek_model,
                    'messages': groq_messages,
                    'max_tokens': 800,
                    'temperature': 0.7
                }
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                if res.status_code == 200:
                    result = res.json()
                    content = result['choices'][0]['message']['content']
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                    result['choices'][0]['message']['content'] = content
                    return Response(result)
                else:
                    print(f"DeepSeek API error: {res.text}. Falling back to Groq.")
            except Exception as e:
                print(f"DeepSeek connection error: {e}. Falling back to Groq.")

        # Priority 2: Groq API
        groq_api_key, groq_model = get_provider_config('GROQ')
        
        if not groq_api_key:
            return Response({'choices': [{'message': {'content': 'ขออภัยด้วยครับ ปัจจุบันบอทไม่ได้รับคีย์เชื่อมต่อบริการ AI (DeepSeek / Groq) ใน .env ครับ 💖'}}], 'model': 'fallback'})
            
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                'Authorization': f"Bearer {groq_api_key}",
                'Content-Type': 'application/json'
            }
            payload = {
                'model': groq_model,
                'messages': groq_messages,
                'max_tokens': 800,
                'temperature': 0.7
            }
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                result = res.json()
                content = result['choices'][0]['message']['content']
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                result['choices'][0]['message']['content'] = content
                return Response(result)
            else:
                return Response({'error': f'AI Service Error: {res.text}'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

class NoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        user = request.user
        try:
            note = Note.objects.get(user=user, lesson_id=lesson_id)
            return Response({'content': note.content})
        except Note.DoesNotExist:
            return Response({'content': ''})

    def post(self, request):
        user = request.user
        lesson_id = request.data.get('lesson_id')
        content = request.data.get('content', '')

        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response({'error': 'ไม่พบบทเรียน'}, status=status.HTTP_404_NOT_FOUND)

        note, created = Note.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'content': content}
        )

        if not created:
            note.content = content
            note.save()

        return Response({
            'message': 'บันทึกสมุดโน้ตส่วนตัวลงฐานข้อมูลสำเร็จ',
            'content': note.content
        })

class GameScoreView(APIView):
    permission_classes = []

    def get(self, request):
        game_mode = request.query_params.get('game_mode', 'kana')
        scores = GameScore.objects.filter(game_mode=game_mode).select_related('user').order_by('-score')[:10]
        
        result = []
        for s in scores:
            name_display = s.user.name or s.user.email.split('@')[0]
            if s.user.nickname:
                name_display = f"{s.user.nickname} ({s.user.name or 'นักเรียน'})"
            result.append({
                'id': s.id,
                'user_name': name_display,
                'score': s.score,
                'game_mode': s.game_mode,
                'created_at': s.created_at.strftime('%d/%m/%Y %H:%M')
            })
        return Response(result)

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'error': 'กรุณาเข้าสู่ระบบก่อนบันทึกคะแนน'}, status=status.HTTP_401_UNAUTHORIZED)
            
        user = request.user
        game_mode = request.data.get('game_mode', 'kana')
        score = request.data.get('score', 0)

        game_score = GameScore.objects.create(
            user=user,
            game_mode=game_mode,
            score=int(score)
        )
        return Response({
            'message': 'บันทึกคะแนนเข้าสู่ตารางคะแนนเรียบร้อย',
            'score': game_score.score
        })

class ResetPasswordView(APIView):
    permission_classes = []

    def post(self, request):
        from users.models import User
        email = request.data.get('email', '').strip()
        phone = request.data.get('phone', '').strip()
        new_password = request.data.get('new_password', '').strip()

        if not email or not new_password:
            return Response({'error': 'กรุณาระบุอีเมลและรหัสผ่านใหม่'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({'error': 'ไม่ชีอีเมลสมาชิกนี้ในระบบ'}, status=status.HTTP_404_NOT_FOUND)

        if phone and user.phone and user.phone.replace('-', '') != phone.replace('-', ''):
            return Response({'error': 'เบอร์โทรศัพท์ไม่ตรงกับข้อมูลในระบบ'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({'message': 'ตั้งรหัสผ่านใหม่สำเร็จ สามารถเข้าสู่ระบบด้วยรหัสผ่านใหม่ได้ทันที!'})

class AdminPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'เฉพาะผู้ดูแลระบบ (Admin) เท่านั้น'}, status=status.HTTP_403_FORBIDDEN)
            
        from payments.models import Payment
        payments = Payment.objects.select_related('user', 'course').order_by('-submitted_at')[:50]
        
        result = []
        for p in payments:
            result.append({
                'id': p.id,
                'user_id': p.user.id,
                'user_name': p.user.name or p.user.email,
                'user_email': p.user.email,
                'user_phone': p.user.phone or '-',
                'course_title': p.course.title,
                'amount': float(p.amount),
                'duration_days': p.duration_days,
                'status': p.status,
                'submitted_at': p.submitted_at.strftime('%d/%m/%Y %H:%M') if p.submitted_at else '-'
            })
        return Response(result)

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'เฉพาะผู้ดูแลระบบ (Admin) เท่านั้น'}, status=status.HTTP_403_FORBIDDEN)

        from payments.models import Payment
        payment_id = request.data.get('payment_id')
        action = request.data.get('action') # 'approve' or 'reject'

        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response({'error': 'ไม่พบรายการชำระเงินนี้'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'approve':
            payment.status = 'approved'
            payment.reviewed_at = timezone.now()
            payment.reviewed_by = request.user
            payment.save()

            # Activate enrollment for user
            enrollment, created = Enrollment.objects.get_or_create(
                user=payment.user,
                course=payment.course,
                defaults={'is_active': True, 'status': 'ACTIVE'}
            )
            enrollment.is_active = True
            enrollment.status = 'ACTIVE'
            if payment.duration_days == 9999:
                enrollment.is_lifetime_video = True
            else:
                enrollment.video_expires_at = timezone.now().date() + timezone.timedelta(days=payment.duration_days)
            enrollment.save()

            return Response({'message': f'อนุมัติสิทธิ์เข้าเรียนเรียบร้อยแล้วสำหรับ {payment.user.email}'})
        else:
            payment.status = 'rejected'
            payment.reviewed_at = timezone.now()
            payment.reviewed_by = request.user
            payment.save()
            return Response({'message': 'ปฏิเสธรายการชำระเงินเรียบร้อยแล้ว'})


def get_araigogu_system_prompt(lang: str, mode: str) -> str:
    if lang == 'JA':
        if mode == 'checker':
            return (
                "คุณคือ \"Araigogu AI — ครูตรวจไวยากรณ์ภาษาญี่ปุ่น\" 🇯🇵\n"
                "== หน้าที่ ==\n"
                "1. วิเคราะห์และตรวจทานประโยคภาษาญี่ปุ่นของผู้เรียนอย่างละเอียด\n"
                "2. ระบุความถูกต้องทางไวยากรณ์ (ถูกต้อง / มีจุดแก้ไข)\n"
                "3. เสนอประโยคที่สละสลวยขึ้นเป็นธรรมชาติ พร้อมคำอ่าน ฟุริงะนะ (Furigana) และคำแปลภาษาไทย\n"
                "4. อธิบายคันจิ ไวยากรณ์ และคำศัพท์ที่เกี่ยวข้องอย่างเข้าใจง่าย"
            )
        elif mode == 'interview':
            return (
                "คุณคือ \"Araigogu AI — กรรมการสัมภาษณ์ภาษาญี่ปุ่น (JLPT Interviewer)\" 🇯🇵\n"
                "== หน้าที่ ==\n"
                "1. สนทนาจำลองการสอบสัมภาษณ์เป็นภาษาญี่ปุ่นสลับคำแปลภาษาไทย\n"
                "2. ถามคำถามสัมภาษณ์ เช่น การแนะนำตัว (自己紹介), งานอดิเรก, เหตุผลที่เรียนภาษาญี่ปุ่น, หรือประสบการณ์\n"
                "3. ประเมินคำตอบของผู้เรียน ให้คำแนะนำในการปรับปรุงไวยากรณ์และคำศัพท์อย่างเป็นมิตร"
            )
        else:
            return (
                "คุณคือ \"น้องริวโซ่ (Ryuso Sense) — Araigogu AI\" 🇯🇵 ผู้ช่วยสอนภาษาญี่ปุ่นประจำ RyuClass\n"
                "== บุคลิก ==\n"
                "เป็นหญิงสาวอายุ 20 ปี น่ารัก สดใส ใจดี กระตือรือร้น ชอบช่วยเหลือ ใช้ Emoji พอเหมาะ\n"
                "== ความเชี่ยวชาญ ==\n"
                "1. สอนภาษาญี่ปุ่นทุกระดับตั้งแต่ 0 ถึง JLPT N5, N4, N3, N2, N1\n"
                "2. อธิบายตัวอักษร ฮิรางานะ คาตาคานะ คันจิ ฟุริงะนะ และไวยากรณ์พร้อมตัวอย่างประโยค\n"
                "3. พูดภาษาไทยเป็นหลัก แทรกคำภาษาญี่ปุ่นที่อ่านเข้าใจง่าย"
            )
    elif lang == 'ZH':
        if mode == 'checker':
            return (
                "คุณคือ \"Araigogu AI — ครูตรวจไวยากรณ์ภาษาจีน (Chinese Grammar Checker)\" 🇨🇳\n"
                "== หน้าที่ ==\n"
                "1. ตรวจสอบประโยคภาษาจีนของผู้เรียนอย่างละเอียด\n"
                "2. ระบุจุดที่ผิดไวยากรณ์ พร้อมแก้ไขเป็นประโยคที่ถูกต้องและเป็นธรรมชาติ\n"
                "3. แสดงพินอิน (Pinyin) กำกับเสียงวรรณยุกต์ และคำแปลภาษาไทยอย่างชัดเจน\n"
                "4. อธิบายลำดับคำ (Word Order) และโครงสร้างไวยากรณ์ภาษาจีน"
            )
        elif mode == 'interview':
            return (
                "คุณคือ \"Araigogu AI — กรรมการสัมภาษณ์ภาษาจีน (Chinese Interviewer)\" 🇨🇳\n"
                "== หน้าที่ ==\n"
                "1. จำลองการสัมภาษณ์งาน/สอบวัดระดับภาษาจีน (HSK Oral Test)\n"
                "2. สนทนาภาษาจีนอย่างเป็นกันเอง พร้อมใส่ Pinyin และคำแปลไทยย่อๆ\n"
                "3. ให้ข้อเสนอแนะในการปรับประโยคภาษาจีนให้เป็นธรรมชาติและถูกต้อง"
            )
        else:
            return (
                "คุณคือ \"เหล่าวซือ (Lao Shi) — Araigogu AI\" 🇨🇳 ผู้ช่วยสอนภาษาจีนประจำ RyuClass\n"
                "== บุคลิก ==\n"
                "เป็นครูสอนภาษาจีนใจดี อบอุ่น สดใส สนุกสนานในการสอนภาษาจีน\n"
                "== ความเชี่ยวชาญ ==\n"
                "1. สอนภาษาจีนตั้งแต่พื้นฐาน พินอิน (Pinyin), ตัวอักษรจีน (Hanzi), เสียงวรรณยุกต์ จนถึง HSK 1-6\n"
                "2. อธิบายคำศัพท์ ไวยากรณ์ ประโยคใช้จริงในชีวิตประจำวันและการทำงาน\n"
                "3. ตอบเป็นภาษาไทยคู่ภาษาจีนพร้อม พินอิน (Pinyin)"
            )
    else: # TH
        if mode == 'checker':
            return (
                "คุณคือ \"Araigogu AI — ผู้เชี่ยวชาญการตรวจทานภาษาไทย (Thai Writing & Grammar Checker)\" 🇹🇭\n"
                "== หน้าที่ ==\n"
                "1. ตรวจสอบสะกดคำ ตัวการันต์ ไวยากรณ์ และการเว้นวรรคภาษาไทย\n"
                "2. ปรับระดับภาษา (ทางการ / กึ่งทางการ / สนทนา) ให้สละสลวยถูกต้องตามหลักภาษาไทย\n"
                "3. อธิบายความหมาย คำตรงข้าม คำราชาศัพท์ และการเลือกใช้คำให้เหมาะสม"
            )
        elif mode == 'interview':
            return (
                "คุณคือ \"Araigogu AI — กรรมการสัมภาษณ์งานภาษาไทย (Thai Interview Simulator)\" 🇹🇭\n"
                "== หน้าที่ ==\n"
                "1. จำลองการสัมภาษณ์งานและทดสอบทักษะการสื่อสารภาษาไทยอย่างมืออาชีพ\n"
                "2. ถามคำถามเชิงลึก และประเมินคำตอบพร้อมให้ข้อเสนอแนะในการตอบที่ประทับใจ"
            )
        else:
            return (
                "คุณคือ \"ครูริว (Kuru Thai) — Araigogu AI\" 🇹🇭 ผู้ช่วยสอนและพัฒนาทักษะภาษาไทย\n"
                "== บุคลิก ==\n"
                "เป็นครูสอนภาษาไทยที่ใจดี รอบรู้ สุภาพ เป็นกันเอง\n"
                "== ความเชี่ยวชาญ ==\n"
                "1. สอนภาษาไทย ไวยากรณ์ การสะกดคำ การเขียนเรียงความ และการสละสลวยประโยค\n"
                "2. ช่วยผู้เรียนทั้งคนไทยและชาวต่างชาติฝึกฝนการใช้ภาษาไทยอย่างถูกต้องสละสลวย"
            )


class AraigoguChatView(APIView):
    def post(self, request):
        session_id = request.data.get('session_id')
        target_language = request.data.get('target_language', 'JA').upper()
        mode = request.data.get('mode', 'chat')
        message = request.data.get('message', '').strip()

        if not message:
            return Response({'error': 'กรุณาระบุข้อความ'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user if request.user and request.user.is_authenticated else None

        if not session_id:
            import uuid
            session_id = f"ara_{uuid.uuid4().hex[:12]}"

        session_obj, created = AraigoguSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': user,
                'target_language': target_language,
                'mode': mode,
                'title': message[:30] + ('...' if len(message) > 30 else '')
            }
        )

        if not created and user and not session_obj.user:
            session_obj.user = user
            session_obj.save()

        if session_obj.target_language != target_language or session_obj.mode != mode:
            session_obj.target_language = target_language
            session_obj.mode = mode
            session_obj.save()

        AraigoguMessage.objects.create(
            session=session_obj,
            sender='user',
            content=message
        )

        system_prompt = get_araigogu_system_prompt(target_language, mode)
        groq_messages = [{'role': 'system', 'content': system_prompt}]

        recent_msgs = AraigoguMessage.objects.filter(session=session_obj).order_by('created_at')[:20]
        for msg in recent_msgs:
            role = 'assistant' if msg.sender == 'assistant' else 'user'
            groq_messages.append({'role': role, 'content': msg.content})

        ai_content = ""
        model_used = ""
        tokens_used = 0

        # 1. DeepSeek API
        deepseek_api_key, deepseek_model = get_provider_config('DEEPSEEK')
        
        if deepseek_api_key:
            try:
                url = "https://api.deepseek.com/chat/completions"
                headers = {
                    'Authorization': f"Bearer {deepseek_api_key}",
                    'Content-Type': 'application/json'
                }
                payload = {
                    'model': deepseek_model,
                    'messages': groq_messages,
                    'max_tokens': 1000,
                    'temperature': 0.7
                }
                res = requests.post(url, json=payload, headers=headers, timeout=20)
                if res.status_code == 200:
                    result = res.json()
                    ai_content = result['choices'][0]['message']['content']
                    ai_content = re.sub(r'<think>.*?</think>', '', ai_content, flags=re.DOTALL).strip()
                    model_used = f"DeepSeek ({deepseek_model})"
                    tokens_used = result.get('usage', {}).get('total_tokens', 0)
                else:
                    print(f"DeepSeek API error: {res.text}. Falling back to Groq.")
            except Exception as e:
                print(f"DeepSeek connection error: {e}. Falling back to Groq.")

        # 2. Groq API Fallback
        if not ai_content:
            groq_api_key, groq_model = get_provider_config('GROQ')

            if groq_api_key:
                try:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {
                        'Authorization': f"Bearer {groq_api_key}",
                        'Content-Type': 'application/json'
                    }
                    payload = {
                        'model': groq_model,
                        'messages': groq_messages,
                        'max_tokens': 1000,
                        'temperature': 0.7
                    }
                    res = requests.post(url, json=payload, headers=headers, timeout=20)
                    if res.status_code == 200:
                        result = res.json()
                        ai_content = result['choices'][0]['message']['content']
                        ai_content = re.sub(r'<think>.*?</think>', '', ai_content, flags=re.DOTALL).strip()
                        model_used = f"Groq ({groq_model})"
                        tokens_used = result.get('usage', {}).get('total_tokens', 0)
                except Exception as e:
                    print(f"Groq API connection error: {e}")

        if not ai_content:
            ai_content = "ขออภัยด้วยครับ ปัจจุบันระบบขัดข้องชั่วคราว ไม่สามารถดึงข้อมูลจาก AI Engine (DeepSeek / Groq) ได้ในขณะนี้ 💖"
            model_used = "fallback"

        AraigoguMessage.objects.create(
            session=session_obj,
            sender='assistant',
            content=ai_content,
            model_used=model_used,
            tokens_used=tokens_used
        )

        session_obj.save()

        return Response({
            'session_id': session_obj.session_id,
            'content': ai_content,
            'model_used': model_used,
            'tokens_used': tokens_used,
            'target_language': session_obj.target_language,
            'mode': session_obj.mode
        })


class AraigoguHistoryView(APIView):
    def get(self, request):
        user = request.user if request.user and request.user.is_authenticated else None
        if user:
            sessions = AraigoguSession.objects.filter(user=user)[:30]
        else:
            sessions = AraigoguSession.objects.all()[:15]

        result = []
        for s in sessions:
            msg_count = s.messages.count()
            result.append({
                'session_id': s.session_id,
                'title': s.title,
                'target_language': s.target_language,
                'mode': s.mode,
                'updated_at': s.updated_at.strftime('%Y-%m-%d %H:%M'),
                'message_count': msg_count
            })
        return Response(result)


class AraigoguSessionDetailView(APIView):
    def get(self, request, session_id):
        try:
            session_obj = AraigoguSession.objects.get(session_id=session_id)
        except AraigoguSession.DoesNotExist:
            return Response({'error': 'ไม่พบประวัติสนทนา'}, status=status.HTTP_404_NOT_FOUND)

        msgs = AraigoguMessage.objects.filter(session=session_obj).order_by('created_at')
        messages_data = [{
            'id': m.id,
            'sender': m.sender,
            'content': m.content,
            'model_used': m.model_used,
            'created_at': m.created_at.strftime('%H:%M')
        } for m in msgs]

        return Response({
            'session_id': session_obj.session_id,
            'title': session_obj.title,
            'target_language': session_obj.target_language,
            'mode': session_obj.mode,
            'messages': messages_data
        })

    def delete(self, request, session_id):
        try:
            session_obj = AraigoguSession.objects.get(session_id=session_id)
            session_obj.delete()
            return Response({'message': 'ลบประวัติสนทนาเรียบร้อยแล้ว'})
        except AraigoguSession.DoesNotExist:
            return Response({'error': 'ไม่พบประวัติสนทนา'}, status=status.HTTP_404_NOT_FOUND)


