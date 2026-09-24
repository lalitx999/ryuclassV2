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

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Serve uploaded slips and community images in local development
    re_path(r'^storage/slips/(?P<path>.*)$', serve, {
        'document_root': '/Applications/XAMPP/xamppfiles/htdocs/ryuclass/storage/slips/',
    }),
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

    # ── Payment & Admin APIs ─────────────────────────────
    path('api/payments/upload-slip/', UploadSlipView.as_view(), name='api_upload_slip'),
    path('api/admin/payments/', AdminPaymentsView.as_view(), name='api_admin_payments'),
    path('api/admin/broadcast-email/', BroadcastEmailView.as_view(), name='api_admin_broadcast_email'),
    path('api/admin/send-renewal-reminders/', SendRenewalRemindersView.as_view(), name='api_admin_send_renewal_reminders'),

    # ── RyuCommunity Forum APIs ──────────────────────────
    path('api/community/', include('community.urls')),
]
