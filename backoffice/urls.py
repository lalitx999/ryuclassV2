from django.urls import path
from . import views
from . import actions

app_name = 'backoffice'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password_change/', views.password_view, name='password'),
    path('payments/payment/<str:pk>/review/', views.review_payment, name='payment-review'),
    path('<str:app>/<str:name>/<str:pk>/action/', actions.perform, name='action'),
    path('<str:app>/<str:name>/', views.records, name='list'),
    path('<str:app>/<str:name>/add/', views.edit, name='add'),
    path('<str:app>/<str:name>/<str:pk>/change/', views.edit, name='edit'),
    path('<str:app>/<str:name>/<str:pk>/delete/', views.delete, name='delete'),
    path('<str:app>/<str:name>/<str:pk>/', views.detail, name='detail'),
]
