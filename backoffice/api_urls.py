from django.urls import path
from .api_views import (
    AdminAuthMeView,
    AdminDashboardAPIView,
    AdminPaymentsAPIView,
    AdminPaymentDetailAPIView,
    AdminPaymentReviewAPIView,
    AdminCoursesAPIView,
    AdminLessonDetailAPIView,
    AdminModuleDetailAPIView,
    AdminUsersAPIView,
    AdminUserImportAPIView,
    AdminBroadcastEmailAPIView
)

urlpatterns = [
    path('auth/me/', AdminAuthMeView.as_view(), name='api_admin_auth_me'),
    path('dashboard/', AdminDashboardAPIView.as_view(), name='api_admin_dashboard'),
    path('payments/', AdminPaymentsAPIView.as_view(), name='api_admin_payments_list'),
    path('payments/<int:pk>/', AdminPaymentDetailAPIView.as_view(), name='api_admin_payment_detail'),
    path('payments/<int:pk>/review/', AdminPaymentReviewAPIView.as_view(), name='api_admin_payment_review'),
    path('courses/', AdminCoursesAPIView.as_view(), name='api_admin_courses_list'),
    path('modules/<int:pk>/', AdminModuleDetailAPIView.as_view(), name='api_admin_module_detail'),
    path('lessons/', AdminLessonDetailAPIView.as_view(), name='api_admin_lesson_create'),
    path('lessons/<int:pk>/', AdminLessonDetailAPIView.as_view(), name='api_admin_lesson_detail'),
    path('users/', AdminUsersAPIView.as_view(), name='api_admin_users_list'),
    path('users/import/', AdminUserImportAPIView.as_view(), name='api_admin_users_import'),
    path('users/<int:pk>/', AdminUsersAPIView.as_view(), name='api_admin_users_detail'),
    path('broadcast-email/', AdminBroadcastEmailAPIView.as_view(), name='api_admin_broadcast_email'),
]
