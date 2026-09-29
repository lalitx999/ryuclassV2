from django.contrib import admin
from django.urls import path, re_path, include
from django.views.static import serve
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.views import RegisterView, ProfileView, LoginView, BroadcastEmailView, VerifyEmailView, ResendEmailVerificationView
from courses.views import (
    DashboardView, CourseDetailView, FreeTrialLessonsView, SaveProgressView, 
    ChatBotView, NoteView, GameScoreView, ResetPasswordView, AdminPaymentsView,
    AraigoguChatView, AraigoguHistoryView, AraigoguSessionDetailView,
    SendRenewalRemindersView
)
from quizzes.views import QuizDetailView, SubmitQuizView
from payments.views import UploadSlipView

from django.conf import settings
from django.http import Http404
import os

def serve_slip(request, path):
    primary_dir = getattr(settings, 'SLIPS_STORAGE_DIR', str(settings.BASE_DIR / 'storage' / 'slips'))
    primary_file = os.path.join(primary_dir, path)
    if os.path.exists(primary_file):
        return serve(request, path, document_root=primary_dir)
    
    fallback_dir = str(settings.BASE_DIR / 'storage' / 'slips')
    fallback_file = os.path.join(fallback_dir, path)
    if os.path.exists(fallback_file):
        return serve(request, path, document_root=fallback_dir)
        
    raise Http404("Slip file not found")

def serve_pdf(request, path):
    primary_dir = getattr(settings, 'PDF_STORAGE_DIR', str(settings.BASE_DIR / 'storage' / 'protected_pdfs'))
    primary_file = os.path.join(primary_dir, path)
    if os.path.exists(primary_file):
        return serve(request, path, document_root=primary_dir)

    fallback_dir = str(settings.BASE_DIR / 'storage' / 'protected_pdfs')
    fallback_file = os.path.join(fallback_dir, path)
    if os.path.exists(fallback_file):
        return serve(request, path, document_root=fallback_dir)

    raise Http404("PDF file not found")

urlpatterns = [
    path('admin/', include('backoffice.urls')),
    
    # Serve uploaded slips, PDFs, and community images in local development
    re_path(r'^storage/slips/(?P<path>.*)$', serve_slip),
    re_path(r'^storage/protected_pdfs/(?P<path>.*)$', serve_pdf),
    re_path(r'^storage/community/(?P<path>.*)$', serve, {
        'document_root': '/Users/tanchonl/Documents/ryu_new/backend/storage/community/',
    }),
    
    # ── JWT Authentication APIs ──────────────────────────
    path('api/auth/register/', RegisterView.as_view(), name='api_register'),
    path('api/auth/verify-email/', VerifyEmailView.as_view(), name='api_verify_email'),
    path('api/auth/resend-verification/', ResendEmailVerificationView.as_view(), name='api_resend_email_verification'),
    path('api/auth/login/', LoginView.as_view(), name='api_login'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('api/auth/profile/', ProfileView.as_view(), name='api_profile'),
    path('api/auth/reset-password/', ResetPasswordView.as_view(), name='api_reset_password'),
    
    # ── Student Learning APIs ────────────────────────────
    path('api/courses/free-trial/', FreeTrialLessonsView.as_view(), name='api_free_trial'),
    path('api/courses/dashboard/', DashboardView.as_view(), name='api_courses_dashboard'),
    path('api/courses/<int:course_id>/', CourseDetailView.as_view(), name='api_course_detail'),
    path('api/courses/save-progress/', SaveProgressView.as_view(), name='api_save_progress'),
    path('api/courses/notes/<int:lesson_id>/', NoteView.as_view(), name='api_get_note'),
    path('api/courses/notes/save/', NoteView.as_view(), name='api_save_note'),
    path('api/courses/chatbot/', ChatBotView.as_view(), name='api_chatbot'),

    # ── Araigogu AI Engine APIs ──────────────────────────
    path('api/araigogu/chat/', AraigoguChatView.as_view(), name='api_araigogu_chat'),
    path('api/araigogu/history/', AraigoguHistoryView.as_view(), name='api_araigogu_history'),
    path('api/araigogu/sessions/<str:session_id>/', AraigoguSessionDetailView.as_view(), name='api_araigogu_session_detail'),
    
    # ── Quiz APIs ────────────────────────────────────────
    path('api/quizzes/lesson/<int:lesson_id>/', QuizDetailView.as_view(), name='api_quiz_detail'),
    path('api/quizzes/submit/', SubmitQuizView.as_view(), name='api_quiz_submit'),
    
    # ── Games Leaderboard APIs ───────────────────────────
    path('api/games/leaderboard/', GameScoreView.as_view(), name='api_game_leaderboard'),
    path('api/games/submit-score/', GameScoreView.as_view(), name='api_game_submit_score'),

    # ── Payment & Admin REST APIs (DRF) ─────────────────
    path('api/payments/upload-slip/', UploadSlipView.as_view(), name='api_upload_slip'),
    path('api/admin/', include('backoffice.api_urls')),
    path('api/admin/send-renewal-reminders/', SendRenewalRemindersView.as_view(), name='api_admin_send_renewal_reminders'),

    # ── RyuCommunity Forum APIs ──────────────────────────
    path('api/community/', include('community.urls')),
]
